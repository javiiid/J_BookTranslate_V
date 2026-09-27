# ============================================================
# app/pipeline/pipeline.py
# ============================================================
"""
Main translation pipeline for KALIMA.

Responsibilities
----------------
- Process EPUB files
- Process PDF files
- Create and resume translation jobs
- Manage translation state
- Handle batch status checks
- Save translation progress
- Reassemble translated EPUB files
- Create translated PDF files
- Handle Ctrl+C safely
- Clean temporary files after successful processing
"""

import signal
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.jobs.state import (
    load_job_state,
    save_chunks,
    save_translations,
    ensure_temp_structure,
)

from app.jobs.manager import select_resumable_job

from app.jobs.cleanup import cleanup_files

from app.translation.translator import (
    process_translations,
    load_test_translations,
)

from app.translation.batch import check_batch_status

from app.pipeline.epub_handler import EPUBHandler
from app.pipeline.epub_pipeline import reassemble_translation

from app.core.paths import (
    create_job_id,
)

from app.core.logging import log_progress
from app.core.validation import ensure_disk_space, validate_book

from app.core.exceptions import handle_interrupt

from app.output.formats import generate_outputs
from app.output.markers import strip_markers
from app.output.segments import build_segments
from app.pipeline.quality_scorer import make_scorer


UTC = timezone.utc


# ============================================================
# HELPERS
# ============================================================

def _utc_timestamp():
    """
    Return the current UTC timestamp as a readable string.
    """
    return datetime.now(UTC).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _create_job(
    input_path,
    from_lang,
    to_lang,
    model,
):
    """
    Create a new translation job and its temporary structure.

    Returns
    -------
    tuple
        (job_id, paths)
    """

    job_id = create_job_id(
        input_path,
        from_lang,
        to_lang,
        model,
    )

    paths = ensure_temp_structure(job_id)

    return job_id, paths


def _cleanup_job(
    client,
    paths,
    input_file_id=None,
    status=None,
    debug=False,
):
    """
    Remove temporary files and remote batch files.

    In debug mode nothing is deleted.
    """

    if debug:
        print(
            "Debug mode enabled: "
            "temporary files will be preserved "
            "[translate]"
        )
        return

    if not paths:
        return

    file_ids = []

    if input_file_id:
        file_ids.append(input_file_id)

    if status is not None:
        output_file_id = getattr(
            status,
            "output_file_id",
            None,
        )

        if output_file_id:
            file_ids.append(output_file_id)

    job_dir = paths.get("job_dir")

    if not job_dir:
        return

    print(
        f"Cleaning up job directory: "
        f"{job_dir} [translate]"
    )

    cleanup_files(
        client,
        file_ids,
        temp_dir=job_dir,
        keep_temp=False,
    )


def _print_job_start(
    job_id,
    model,
    resumed=False,
):
    """
    Print standard job startup information.
    """

    print()

    if resumed:
        print(
            f"Resuming job: {job_id} [translate]"
        )
    else:
        print(
            f"Starting new job: {job_id} [translate]"
        )

    print(
        f"Started at: {_utc_timestamp()} UTC "
        f"[translate]"
    )

    print(
        f"Using model: {model} [translate]"
    )


# ============================================================
# EPUB PIPELINE
# ============================================================

def _translate_epub(
    client,
    input_path,
    output_path,
    from_lang,
    to_lang,
    mode,
    model,
    fast,
    resume_job_id,
    debug,
    translation_prompt,
    output_formats=None,
    stop_event=None,
    on_job_started=None,
    style_preset=None,
):
    """
    Execute the complete EPUB translation pipeline.
    """

    # Python only permits signal handlers in the interpreter's main thread.
    # The CLI runs there, while the local web UI deliberately runs jobs in a
    # worker thread so its request handler remains responsive.
    can_manage_signals = threading.current_thread() is threading.main_thread()
    original_sigint_handler = (
        signal.getsignal(signal.SIGINT)
        if can_manage_signals
        else None
    )

    interrupted = False
    success = False

    manifest_outputs = None

    input_file_id = None
    status = None

    paths = None
    job_id = None
    existing_state = None

    all_chunks = []
    chapter_map = {}
    translations = {}

    # chunk_id -> plain text of the preceding chunks. Empty unless semantic
    # chunking is enabled; see app/pipeline/semantic_chunker.py.
    chunk_contexts = {}

    try:

        # ====================================================
        # RESUME JOB
        # ====================================================

        if mode in (
            "resume",
            "resumebatch",
        ) and resume_job_id is None:

            resume_job_id = select_resumable_job(
                input_path,
                from_lang,
                to_lang,
                model,
                mode,
            )

            if resume_job_id is None:
                print(
                    "No job selected. "
                    "Translation cancelled. "
                    "[translate]"
                )
                return

        # ====================================================
        # EXISTING JOB
        # ====================================================

        if resume_job_id:

            job_id = resume_job_id

            paths = ensure_temp_structure(
                job_id
            )

            existing_state = load_job_state(
                paths
            )

            if not existing_state:

                print(
                    f"No valid state found for job "
                    f"{job_id}. [translate]"
                )

                print(
                    "Starting a new translation job. "
                    "[translate]"
                )

                job_id, paths = _create_job(
                    input_path,
                    from_lang,
                    to_lang,
                    model,
                )

                resume_job_id = None

            else:

                _print_job_start(
                    job_id,
                    model,
                    resumed=True,
                )

        # ====================================================
        # NEW JOB
        # ====================================================

        else:

            job_id, paths = _create_job(
                input_path,
                from_lang,
                to_lang,
                model,
            )

            _print_job_start(
                job_id,
                model,
                resumed=False,
            )

        # ====================================================
        # LOG
        # ====================================================

        if on_job_started:
            on_job_started(job_id, paths)

        log_progress(
            paths,
            (
                "Resuming"
                if resume_job_id
                else "Starting"
            )
            + f" translation job: {job_id}",
        )

        # ====================================================
        # SIGNAL HANDLER
        # ====================================================

        if can_manage_signals:
            signal.signal(
                signal.SIGINT,
                handle_interrupt,
            )

        # ====================================================
        # LOAD EXISTING STATE
        # ====================================================

        if resume_job_id and existing_state:

            print()
            print(
                "Resuming from previous state "
                "[translate]"
            )

            all_chunks = existing_state.get(
                "chunks",
                [],
            )

            chapter_map = existing_state.get(
                "chapter_map",
                {},
            )

            # Preceding-chunk context, keyed by chunk id. Saved with the job so a
            # resumed run gives the model the same context the first run did --
            # otherwise a resumed book would quietly translate its later chunks
            # blind, which is the whole point of the feature.
            chunk_contexts = existing_state.get(
                "chunk_contexts",
                {},
            )

            translations = existing_state.get(
                "translations",
                {},
            )

            print(
                f"Total chunks: "
                f"{len(all_chunks)} [translate]"
            )

            print(
                f"Completed translations: "
                f"{len(translations)} [translate]"
            )

        # ====================================================
        # BUILD NEW EPUB CHUNKS
        # ====================================================

        else:

            print()
            print(
                "Building EPUB chunks... "
                "[translate]"
            )

            all_chunks, chapter_map, chunk_contexts = (
                EPUBHandler.build_chunks(
                    input_path
                )
            )

            if not all_chunks:

                print(
                    "No translatable chunks were "
                    "found in the EPUB. [translate]"
                )

                return

            save_chunks(
                paths,
                all_chunks,
                chapter_map,
                chunk_contexts,
            )

            translations = {}

            print(
                f"Total chunks created: "
                f"{len(all_chunks)} [translate]"
            )

        # ====================================================
        # DETERMINE MODE
        # ====================================================

        if not mode:

            mode = (
                "fast"
                if fast
                else "batch"
            )

        print(
            f"Processing mode: "
            f"{mode} [translate]"
        )

        # ====================================================
        # TEST MODE
        # ====================================================

        test_translations = None

        if mode == "test":

            test_translations = (
                load_test_translations(
                    input_path
                )
            )

            if test_translations is None:

                print(
                    "No test translations found. "
                    "[translate]"
                )

                return

        # ====================================================
        # TRANSLATION
        # ====================================================

        print()
        print(
            "=" * 60
        )
        print(
            "Starting translation..."
        )
        print(
            "=" * 60
        )

        translations, input_file_id, status = (
            process_translations(
                client,
                all_chunks,
                translations,
                mode,
                from_lang,
                to_lang,
                paths,
                model=model,
                test_translations=test_translations,
                debug=debug,
                chapter_map=chapter_map,
                filetype="epub",
                translation_prompt=translation_prompt,
                stop_event=stop_event,
                style_preset=style_preset,
                chunk_contexts=chunk_contexts,
            )
        )

        print(
            f"Final translation count: "
            f"{len(translations)} "
            f"[translate]"
        )

        # ====================================================
        # SAVE STATE
        # ====================================================

        save_translations(
            paths,
            translations,
        )

        # ====================================================
        # BATCH MODE
        # ====================================================

        if mode in (
            "batch",
            "resumebatch",
        ):

            if status is not None:

                current_status = getattr(
                    status,
                    "status",
                    None,
                )

                print(
                    f"Batch status: "
                    f"{current_status} "
                    f"[translate]"
                )

                # Batch is not finished yet.
                if current_status in (
                    "validating",
                    "in_progress",
                    "finalizing",
                    "cancelling",
                ):

                    print(
                        "Batch is still processing. "
                        "[translate]"
                    )

                    print(
                        "Run --mode batchcheck "
                        "later to check the result. "
                        "[translate]"
                    )

                    return

        # ====================================================
        # EMPTY TRANSLATION CHECK
        # ====================================================

        if not translations:

            print(
                "No translations available. "
                "Output file will not be created. "
                "[translate]"
            )

            return

        # ============================================================
        # EXTRA OUTPUT FORMATS
        # ============================================================

        if output_formats:

            print()
            print(
                "Generating additional output "
                "formats... [translate]"
            )

            output_result = generate_outputs(
                build_segments(
                    all_chunks,
                    translations,
                    chapter_map,
                    filetype="epub",
                ),
                requested=output_formats,
                output_dir=output_path.parent,
                base_name=output_path.stem,
                filetype="epub",
                title=input_path.stem,
                to_lang=to_lang,
                scorer=make_scorer(
                    output_formats,
                    client=client,
                    model=model,
                    source_lang=from_lang,
                    target_lang=to_lang,
                    filetype="epub",
                    all_chunks=all_chunks,
                    translations=translations,
                    paths=paths,
                    stop_event=stop_event,
                ),
            )

            translations = {
                chunk_id: strip_markers(value)
                for chunk_id, value
                in translations.items()
            }

            manifest_outputs = output_result

            for name, item_path in sorted(
                output_result["generated"].items()
            ):

                print(
                    f"  {name:<18}: {item_path} "
                    f"[translate]"
                )

            if output_result["flagged"]:

                print(
                    f"  QA: {output_result['flagged']} "
                    "flagged segment(s). [translate]"
                )

            if output_result.get("quality"):

                print(
                    f"  Quality: "
                    f"{output_result['quality']['flagged_count']} "
                    f"of "
                    f"{output_result['quality']['total_chunks']} "
                    f"chunks flagged "
                    f"[translate]"
                )

        # ====================================================
        # REASSEMBLE EPUB
        # ====================================================

        print()
        print(
            "Reassembling translated EPUB... "
            "[translate]"
        )

        reassemble_translation(
            input_path,
            output_path,
            chapter_map,
            translations,
        )

        print(
            f"Translated EPUB saved to: "
            f"{output_path} [translate]"
        )

        success = True

    except KeyboardInterrupt:

        interrupted = True

        print()
        print(
            "=" * 60
        )
        print(
            "TRANSLATION INTERRUPTED"
        )
        print(
            "=" * 60
        )

        print(
            "Current translation state "
            "has been preserved. [translate]"
        )

        print(
            "Run again with --mode resume "
            "to continue. [translate]"
        )

    finally:

        # ====================================================
        # RESTORE SIGNAL HANDLER
        # ====================================================

        if can_manage_signals:
            signal.signal(
                signal.SIGINT,
                original_sigint_handler,
            )

        # ====================================================
        # DO NOT CLEAN INTERRUPTED JOB
        # ====================================================

        if interrupted:

            print(
                "Temporary files preserved "
                "for resume. [translate]"
            )

            return

        # ====================================================
        # CLEANUP
        # ====================================================

        if success:

            _cleanup_job(
                client,
                paths,
                input_file_id,
                status,
                debug,
            )

            print()
            print(
                "Processing completed "
                "successfully. [translate]"
            )

        else:

            print()
            print(
                "Processing did not complete "
                "successfully. [translate]"
            )

            print(
                "Temporary files have been "
                "preserved for debugging/resume. "
                "[translate]"
            )


    return manifest_outputs
# ============================================================
# EPUB BATCH CHECK
# ============================================================

def _check_epub_batch(
    client,
    input_path,
    output_path,
    from_lang,
    to_lang,
    model,
    debug,
    output_formats=None,
):
    """
    Check the status of an existing EPUB batch job.
    """

    print()
    print(
        "=" * 60
    )
    print(
        "CHECKING BATCH STATUS"
    )
    print(
        "=" * 60
    )

    state, state_file, status = (
        check_batch_status(
            client,
            debug,
        )
    )

    if not state:

        print(
            "No batch state found. "
            "[translate]"
        )

        return

    if status is None:

        print(
            "Batch status could not be retrieved. "
            "[translate]"
        )

        return

    current_status = getattr(
        status,
        "status",
        None,
    )

    print(
        f"Batch status: "
        f"{current_status} [translate]"
    )

    # ========================================================
    # STILL RUNNING
    # ========================================================

    if current_status not in (
        "completed",
        "failed",
        "expired",
        "cancelled",
    ):

        print(
            "Batch is still running. "
            "[translate]"
        )

        print(
            "Run batchcheck again later. "
            "[translate]"
        )

        return

    # ========================================================
    # FAILED
    # ========================================================

    if current_status != "completed":

        print(
            f"Batch finished with status: "
            f"{current_status} [translate]"
        )

        print(
            "Temporary files have been "
            "preserved. [translate]"
        )

        return

    # ========================================================
    # COMPLETED
    # ========================================================

    timestamp = state.get(
        "timestamp"
    )

    if not timestamp:

        print(
            "Batch state does not contain "
            "a valid timestamp. [translate]"
        )

        return

    job_id = create_job_id(
        input_path,
        from_lang,
        to_lang,
        model,
        timestamp,
    )

    paths = ensure_temp_structure(
        job_id
    )

    chapter_map_data = state.get(
        "job_metadata",
        {},
    ).get(
        "chapter_map",
        {},
    )

    chapter_map = {
        chunk_id: (
            data["item"],
            data["pos"],
        )
        for chunk_id, data
        in chapter_map_data.items()
    }

    translations, input_file_id, final_status = (
        process_translations(
            client,
            [],
            {},
            "batchcheck",
            from_lang,
            to_lang,
            {
                key: Path(value)
                for key, value
                in state["paths"].items()
            },
            model=model,
            debug=debug,
            chapter_map=chapter_map_data,
            filetype="epub",
        )
    )

    if not translations:

        print(
            "No translations were returned "
            "from the completed batch. "
            "[translate]"
        )

        return

    # ========================================================
    # SAVE
    # ========================================================

    save_translations(
        paths,
        translations,
    )

        # ============================================================
        # EXTRA OUTPUT FORMATS
        # ============================================================

    if output_formats:

        print()
        print(
            "Generating additional output "
            "formats... [translate]"
        )

        state_loaded = load_job_state(paths) or {}

        output_result = generate_outputs(
            build_segments(
                state_loaded.get("chunks", []),
                translations,
                chapter_map,
                filetype="epub",
            ),
            requested=output_formats,
            output_dir=output_path.parent,
            base_name=output_path.stem,
            filetype="epub",
            title=input_path.stem,
            to_lang=to_lang,
            scorer=make_scorer(
                output_formats,
                client=client,
                model=model,
                source_lang=from_lang,
                target_lang=to_lang,
                filetype="epub",
                all_chunks=state_loaded.get("chunks", []),
                translations=translations,
                paths=paths,
            ),
        )

        translations = {
            chunk_id: strip_markers(value)
            for chunk_id, value
            in translations.items()
        }

        for name, item_path in sorted(
            output_result["generated"].items()
        ):

            print(
                f"  {name:<18}: {item_path} "
                f"[translate]"
            )

        if output_result["flagged"]:

            print(
                f"  QA: {output_result['flagged']} "
                "flagged segment(s). [translate]"
            )

    # ========================================================
    # REASSEMBLE
    # ========================================================

    reassemble_translation(
        input_path,
        output_path,
        chapter_map,
        translations,
    )

    print()
    print(
        f"Translated EPUB saved to: "
        f"{output_path} [translate]"
    )

    # ========================================================
    # CLEANUP
    # ========================================================

    if debug:

        print(
            "Debug mode: batch files preserved. "
            "[translate]"
        )

        return

    file_ids = []

    if input_file_id:
        file_ids.append(
            input_file_id
        )

    if final_status is not None:

        output_file_id = getattr(
            final_status,
            "output_file_id",
            None,
        )

        if output_file_id:
            file_ids.append(
                output_file_id
            )

    job_dir = Path(
        state["paths"]["job_dir"]
    )

    cleanup_files(
        client,
        file_ids,
        temp_dir=job_dir,
        keep_temp=False,
    )

    try:

        if state_file.exists():

            state_file.unlink()

            print(
                "Batch state file removed. "
                "[translate]"
            )

    except Exception as exc:

        print(
            f"Warning: Could not remove "
            f"batch state file: {exc} "
            f"[translate]"
        )


# ============================================================
# PDF PIPELINE
# ============================================================

def _translate_pdf(
    client,
    input_path,
    output_path,
    from_lang,
    to_lang,
    mode,
    model,
    debug,
    translation_prompt,
    output_formats=None,
    stop_event=None,
    on_job_started=None,
    style_preset=None,
):
    """
    Execute the PDF processing pipeline.

    Important:
    PDFHandler.transcribe_pdf() is responsible for
    extracting/OCRing the PDF.

    The extracted chunks are then sent through
    process_translations().
    """

    from app.pipeline.pdf_handler import PDFHandler

    success = False

    manifest_outputs = None

    paths = None
    input_file_id = None
    status = None

    try:

        # ====================================================
        # CREATE JOB
        # ====================================================

        job_id, paths = _create_job(
            input_path,
            from_lang,
            to_lang,
            model,
        )

        _print_job_start(
            job_id,
            model,
            resumed=False,
        )

        if on_job_started:
            on_job_started(job_id, paths)

        # ====================================================
        # BATCHCHECK
        # ====================================================

        if mode == "batchcheck":

            print(
                "PDF batchcheck is not implemented "
                "in this pipeline. [translate]"
            )

            return

        # ====================================================
        # TRANSCRIBE PDF
        # ====================================================

        print()
        print(
            "=" * 60
        )
        print(
            "PDF PROCESSING"
        )
        print(
            "=" * 60
        )

        print(
            "Extracting text from PDF... "
            "[translate]"
        )

        all_chunks, chapter_map = (
            PDFHandler.transcribe_pdf(
                client,
                input_path,
                paths,
                dpi=150,
                batch=False,
            )
        )

        if not all_chunks:

            print(
                "No text was extracted from "
                "the PDF. [translate]"
            )

            return

        print(
            f"Extracted {len(all_chunks)} "
            f"chunks/pages. [translate]"
        )

        # ====================================================
        # SAVE CHUNKS
        # ====================================================

        save_chunks(
            paths,
            all_chunks,
            chapter_map,
        )

        # ====================================================
        # TRANSLATION
        # ====================================================

        translations = {}

        print()
        print(
            "=" * 60
        )
        print(
            "TRANSLATING PDF"
        )
        print(
            "=" * 60
        )

        if not mode:

            mode = "fast"

        translations, input_file_id, status = (
            process_translations(
                client,
                all_chunks,
                translations,
                mode,
                from_lang,
                to_lang,
                paths,
                model=model,
                debug=debug,
                chapter_map=chapter_map,
                filetype="pdf",
                translation_prompt=translation_prompt,
                stop_event=stop_event,
                style_preset=style_preset,
            )
        )

        print(
            f"Final translation count: "
            f"{len(translations)} "
            f"[translate]"
        )

        # ====================================================
        # SAVE TRANSLATIONS
        # ====================================================

        save_translations(
            paths,
            translations,
        )

        if not translations:

            print(
                "No PDF translations available. "
                "[translate]"
            )

            return

        # ============================================================
        # EXTRA OUTPUT FORMATS
        # ============================================================

        if output_formats:

            print()
            print(
                "Generating additional output "
                "formats... [translate]"
            )

            output_result = generate_outputs(
                build_segments(
                    all_chunks,
                    translations,
                    chapter_map,
                    filetype="pdf",
                ),
                requested=output_formats,
                output_dir=output_path.parent,
                base_name=output_path.stem,
                filetype="pdf",
                title=input_path.stem,
                to_lang=to_lang,
                scorer=make_scorer(
                    output_formats,
                    client=client,
                    model=model,
                    source_lang=from_lang,
                    target_lang=to_lang,
                    filetype="pdf",
                    all_chunks=all_chunks,
                    translations=translations,
                    paths=paths,
                    stop_event=stop_event,
                ),
            )

            translations = {
                chunk_id: strip_markers(value)
                for chunk_id, value
                in translations.items()
            }

            manifest_outputs = output_result

            for name, item_path in sorted(
                output_result["generated"].items()
            ):

                print(
                    f"  {name:<18}: {item_path} "
                    f"[translate]"
                )

            if output_result["flagged"]:

                print(
                    f"  QA: {output_result['flagged']} "
                    "flagged segment(s). [translate]"
                )

            if output_result.get("quality"):

                print(
                    f"  Quality: "
                    f"{output_result['quality']['flagged_count']} "
                    f"of "
                    f"{output_result['quality']['total_chunks']} "
                    f"chunks flagged "
                    f"[translate]"
                )

        # ====================================================
        # CREATE PDF
        # ====================================================

        if mode == "pdfbilingual":

            print(
                "Creating bilingual PDF... "
                "[translate]"
            )

            PDFHandler.save_bilingual_pdf(
                input_path,
                translations,
                output_path,
            )

        else:

            print(
                "Creating translated PDF... "
                "[translate]"
            )

            PDFHandler.save_translated_pdf(
                translations,
                output_path,
            )

        print()
        print(
            f"Translated PDF saved to: "
            f"{output_path} [translate]"
        )

        print(
            f"Finished at: "
            f"{_utc_timestamp()} UTC "
            f"[translate]"
        )

        success = True

    except KeyboardInterrupt:

        print()
        print(
            "PDF translation interrupted. "
            "Temporary files were preserved. "
            "[translate]"
        )

        print(
            "Run the job again to resume if "
            "your PDF pipeline supports resume. "
            "[translate]"
        )

        return

    finally:

        if success:

            _cleanup_job(
                client,
                paths,
                input_file_id,
                status,
                debug,
            )

            print(
                "PDF processing completed "
                "successfully. [translate]"
            )

        else:

            print(
                "PDF processing did not complete "
                "successfully. Temporary files "
                "were preserved. [translate]"
            )


    return manifest_outputs
# ============================================================
# MAIN TRANSLATE FUNCTION
# ============================================================

def translate(
    client,
    input_path,
    output_path,
    from_lang="EN",
    to_lang="FA",
    mode=None,
    model=None,
    fast=False,
    resume_job_id=None,
    debug=False,
    filetype="epub",
    translation_prompt=None,
    output_formats=None,
    stop_event=None,
    on_job_started=None,
    style_preset=None,
):
    """
    Main translation dispatcher.

    Parameters
    ----------
    client:
        OpenAI-compatible API client.

    input_path:
        Source EPUB/PDF path.

    output_path:
        Destination path.

    from_lang:
        Source language.

    to_lang:
        Target language.

    mode:
        Translation mode.

    model:
        Model name.

    fast:
        Whether fast mode is preferred.

    resume_job_id:
        Existing job ID for resume.

    debug:
        Preserve temporary files.

    filetype:
        epub or pdf.

    translation_prompt:
        Custom/default translation prompt generated
        by app.translation.prompts.
    """

    # ========================================================
    # RESOLVE MODEL
    # ========================================================
    # The signature used to default to "gpt-5.6-terra", so a caller that
    # omitted `model` silently overrode the user's choice. config.yaml is now
    # the single source of truth, with DEFAULT_MODEL as the fallback.
    if model is None:
        from app.core.models import resolve_default_model
        model = resolve_default_model()

    # ========================================================
    # NORMALIZE FILETYPE
    # ========================================================

    filetype = (
        str(filetype)
        .lower()
        .lstrip(".")
    )

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    # Validate the document and available resources before creating a job or
    # making an API request. This catches corrupt archives and disk exhaustion
    # early, while leaving resumable state untouched.
    validate_book(input_path)
    ensure_disk_space(output_path, required_bytes=max(input_path.stat().st_size * 3, 100 * 1024 * 1024))

    # ========================================================
    # VALIDATE INPUT
    # ========================================================

    if not input_path.exists():

        raise FileNotFoundError(
            f"Input file does not exist: "
            f"{input_path}"
        )

    if not input_path.is_file():

        raise ValueError(
            f"Input path is not a file: "
            f"{input_path}"
        )

    # ========================================================
    # VALIDATE FILETYPE
    # ========================================================

    if filetype not in (
        "epub",
        "pdf",
    ):

        raise ValueError(
            "Unsupported file type: "
            f"{filetype}. "
            "Only EPUB and PDF are supported."
        )

    # ========================================================
    # CREATE OUTPUT DIRECTORY
    # ========================================================

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # DEFAULT MODE
    # ========================================================

    if mode is None:

        mode = (
            "fast"
            if fast
            else "batch"
        )

    # ========================================================
    # PRINT PIPELINE INFORMATION
    # ========================================================

    print()
    print(
        "=" * 60
    )
    print(
        "KALIMA PIPELINE"
    )
    print(
        "=" * 60
    )

    print(
        f"Input     : {input_path}"
    )

    print(
        f"Output    : {output_path}"
    )

    print(
        f"File type : {filetype}"
    )

    print(
        f"From      : {from_lang}"
    )

    print(
        f"To        : {to_lang}"
    )

    print(
        f"Model     : {model}"
    )

    print(
        f"Mode      : {mode}"
    )

    print(
        f"Debug     : {debug}"
    )

    print(
        "=" * 60
    )

    # ========================================================
    # EPUB
    # ========================================================

    if filetype == "epub":

        # ----------------------------------------------------
        # BATCH CHECK
        # ----------------------------------------------------

        if mode == "batchcheck":

            return _check_epub_batch(
                client=client,
                input_path=input_path,
                output_path=output_path,
                from_lang=from_lang,
                to_lang=to_lang,
                model=model,
                debug=debug,
                output_formats=output_formats,
            )

        # ----------------------------------------------------
        # NORMAL EPUB TRANSLATION
        # ----------------------------------------------------

        return _translate_epub(
            client=client,
            input_path=input_path,
            output_path=output_path,
            from_lang=from_lang,
            to_lang=to_lang,
            mode=mode,
            model=model,
            fast=fast,
            resume_job_id=resume_job_id,
            debug=debug,
            translation_prompt=translation_prompt,
            output_formats=output_formats,
            stop_event=stop_event,
            on_job_started=on_job_started,
        style_preset=style_preset,
        )

    # ========================================================
    # PDF
    # ========================================================

    if filetype == "pdf":

        return _translate_pdf(
            client=client,
            input_path=input_path,
            output_path=output_path,
            from_lang=from_lang,
            to_lang=to_lang,
            mode=mode,
            model=model,
            debug=debug,
            translation_prompt=translation_prompt,
            output_formats=output_formats,
            stop_event=stop_event,
            on_job_started=on_job_started,
        style_preset=style_preset,
        )

    # ========================================================
    # SAFETY FALLBACK
    # ========================================================

    raise ValueError(
        f"Unsupported file type: {filetype}"
    )