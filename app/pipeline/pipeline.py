import signal
from datetime import datetime, timezone
from pathlib import Path

from app.jobs.state import (
    load_job_state,
    save_chunks,
    save_translations,
    ensure_temp_structure,
)

from app.jobs.manager import (
    select_resumable_job,
)

from app.jobs.cleanup import (
    cleanup_files,
)

from app.translation.translator import (
    process_translations,
    load_test_translations,
)

from app.translation.batch import (
    check_batch_status,
)

from app.pipeline.epub_handler import EPUBHandler
from app.pipeline.epub_pipeline import reassemble_translation

from app.core.paths import (
    create_job_id,
    ensure_dir,
)

from app.core.logging import (
    log_progress,
)

from app.core.exceptions import (
    handle_interrupt,
)


UTC = timezone.utc


def translate(
    client,
    input_path,
    output_path,
    from_lang='EN',
    to_lang='FA',
    mode=None,
    model='gpt-5.6-terra',
    fast=False,
    resume_job_id=None,
    debug=False,
    filetype='epub'
):

    success = False

    # ============================================================
    # EPUB
    # ============================================================

    if filetype == 'epub':

        # --------------------------------------------------------
        # Batch Check
        # --------------------------------------------------------

        if mode == 'batchcheck':

            state, state_file, status = check_batch_status(
                client,
                debug
            )

            if not state:
                return

            timestamp = state['timestamp']

            job_id = create_job_id(
                input_path,
                from_lang,
                to_lang,
                model,
                timestamp
            )

            paths = ensure_temp_structure(job_id)

            translations, input_file_id, status = process_translations(
                client,
                [],
                {},
                mode,
                from_lang,
                to_lang,
                {
                    k: Path(v)
                    for k, v in state['paths'].items()
                },
                model=model,
                debug=debug,
                chapter_map=state['job_metadata']['chapter_map'],
                filetype=filetype
            )

            if translations:

                chapter_map = {
                    chunk_id: (
                        data["item"],
                        data["pos"]
                    )
                    for chunk_id, data
                    in state['job_metadata']['chapter_map'].items()
                }

                reassemble_translation(
                    input_path,
                    output_path,
                    chapter_map,
                    translations
                )

                print(
                    f"Translated EPUB saved to "
                    f"{output_path} [translate]"
                )

                # IMPORTANT:
                # استفاده از debug به جای DEBUG
                if not debug:

                    print(
                        "Cleaning up job directory and "
                        "batch files... [translate]"
                    )

                    file_ids = []

                    if input_file_id:
                        file_ids.append(input_file_id)

                    if status and status.output_file_id:
                        file_ids.append(
                            status.output_file_id
                        )

                    job_dir = Path(
                        state['paths']['job_dir']
                    )

                    cleanup_files(
                        client,
                        file_ids,
                        temp_dir=job_dir,
                        keep_temp=False
                    )

                    try:

                        if state_file.exists():
                            state_file.unlink()

                            print(
                                "Cleaned up batch state file "
                                "[translate]"
                            )

                    except Exception as e:

                        print(
                            f"Warning: Could not remove "
                            f"batch state file: {e} "
                            f"[translate]"
                        )

                else:

                    print(
                        "Debug mode: Preserving "
                        "temporary files [translate]"
                    )

            return

        # --------------------------------------------------------
        # Signal Handler
        # --------------------------------------------------------

        original_handler = signal.signal(
            signal.SIGINT,
            handle_interrupt
        )

        interrupted = False

        # --------------------------------------------------------
        # Test Translations
        # --------------------------------------------------------

        test_translations = None

        if mode == 'test':

            test_translations = load_test_translations(
                input_path
            )

            if test_translations is None:
                return

        input_file_id = None
        status = None

        # --------------------------------------------------------
        # Main EPUB Processing
        # --------------------------------------------------------

        try:

            timestamp = datetime.now(
                UTC
            ).strftime(
                '%Y%m%d_%H%M%S'
            )

            # ----------------------------------------------------
            # Resume Job
            # ----------------------------------------------------

            if (
                mode in ['resume', 'resumebatch']
                and resume_job_id is None
            ):

                resume_job_id = select_resumable_job(
                    input_path,
                    from_lang,
                    to_lang,
                    model,
                    mode
                )

                if resume_job_id is None:

                    print(
                        "User chose to quit. [translate]"
                    )

                    return

            # ----------------------------------------------------
            # Existing Job
            # ----------------------------------------------------

            if resume_job_id:

                job_id = resume_job_id

                print(
                    f"Resuming job: {job_id} [translate]"
                )

                paths = ensure_temp_structure(
                    job_id
                )

                existing_state = load_job_state(
                    paths
                )

                if not existing_state:

                    print(
                        f"No valid state found in "
                        f"{job_id}, starting fresh "
                        f"translation [translate]"
                    )

                    resume_job_id = None

                    job_id = create_job_id(
                        input_path,
                        from_lang,
                        to_lang,
                        model
                    )

                    paths = ensure_temp_structure(
                        job_id
                    )

                    existing_state = None

            # ----------------------------------------------------
            # New Job
            # ----------------------------------------------------

            else:

                job_id = create_job_id(
                    input_path,
                    from_lang,
                    to_lang,
                    model
                )

                print(
                    f"Starting new job: "
                    f"{job_id} [translate]"
                )

                paths = ensure_temp_structure(
                    job_id
                )

                existing_state = None

            # ----------------------------------------------------
            # Logging
            # ----------------------------------------------------

            log_progress(
                paths,
                (
                    "Resuming"
                    if resume_job_id
                    else "Starting"
                )
                + f" translation job: {job_id}"
            )

            success = False

            all_chunks = []
            chapter_map = {}
            translations = {}

            # ----------------------------------------------------
            # Processing
            # ----------------------------------------------------

            try:

                print(
                    f"Started at: "
                    f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} "
                    f"UTC [translate]"
                )

                print(
                    f"Using model: {model} "
                    f"[translate]"
                )

                # ------------------------------------------------
                # Resume Existing State
                # ------------------------------------------------

                if resume_job_id:

                    print(
                        "\nResuming from previous state: "
                        "[translate]"
                    )

                    print(
                        f"Total chunks: "
                        f"{existing_state['chunks_total']} "
                        f"[translate]"
                    )

                    print(
                        f"Completed translations: "
                        f"{len(existing_state.get('translations', {}))} "
                        f"[translate]"
                    )

                    all_chunks = existing_state[
                        'chunks'
                    ]

                    chapter_map = existing_state[
                        'chapter_map'
                    ]

                    translations = existing_state.get(
                        'translations',
                        {}
                    )

                    print(
                        f"Resumed with "
                        f"{len(translations)} "
                        f"existing translations "
                        f"[translate]"
                    )

                # ------------------------------------------------
                # New EPUB
                # ------------------------------------------------

                else:

                    all_chunks, chapter_map = (
                        EPUBHandler.build_chunks(
                            input_path
                        )
                    )

                    save_chunks(
                        paths,
                        all_chunks,
                        chapter_map
                    )

                    translations = {}

                print(
                    f"Total chunks to process: "
                    f"{len(all_chunks)} [translate]"
                )

                # ------------------------------------------------
                # Determine Mode
                # ------------------------------------------------

                if not mode:

                    mode = (
                        'fast'
                        if fast
                        else 'batch'
                    )

                print(
                    f"Processing mode: "
                    f"{mode} [translate]"
                )

                # ------------------------------------------------
                # Translation
                # ------------------------------------------------

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
                        filetype=filetype
                    )
                )

                print(
                    f"Final translation count: "
                    f"{len(translations)} "
                    f"[translate]"
                )

                # ------------------------------------------------
                # Save Translation State
                # ------------------------------------------------

                save_translations(
                    paths,
                    translations
                )

                # ------------------------------------------------
                # Empty Translation Check
                # ------------------------------------------------

                if len(translations) == 0:

                    print(
                        "No translations available. "
                        "Exiting without creating "
                        "output file. [translate]"
                    )

                    return

                # ------------------------------------------------
                # Reassemble EPUB
                # ------------------------------------------------

                reassemble_translation(
                    input_path,
                    output_path,
                    chapter_map,
                    translations
                )

                print(
                    f"Translated EPUB saved to "
                    f"{output_path} [translate]"
                )

                success = True

            except KeyboardInterrupt:

                interrupted = True

                print(
                    "\nInterrupted by user. "
                    "Progress is saved and can be "
                    "resumed with --mode resume "
                    "[translate]"
                )

                return

            except Exception as e:

                print(
                    f"Error during processing: "
                    f"{e} [translate]"
                )

                raise

        finally:

            signal.signal(
                signal.SIGINT,
                original_handler
            )

            # ----------------------------------------------------
            # Interrupted
            # ----------------------------------------------------

            if interrupted:
                return

            # ----------------------------------------------------
            # Cleanup
            # ----------------------------------------------------

            # FIX:
            # DEBUG -> debug
            keep_temp = debug or not success

            # FIX:
            # DEBUG -> debug
            if not debug:

                print(
                    f"Cleaning up job directory: "
                    f"{paths['job_dir']} [translate]"
                )

                file_ids = []

                if input_file_id:
                    file_ids.append(
                        input_file_id
                    )

                if status and status.output_file_id:
                    file_ids.append(
                        status.output_file_id
                    )

                cleanup_files(
                    client,
                    file_ids,
                    temp_dir=paths['job_dir'],
                    keep_temp=keep_temp
                )

            else:

                print(
                    f"Preserving temporary files "
                    f"(keep_temp={keep_temp}) "
                    f"[translate]"
                )

            # ----------------------------------------------------
            # Final Status
            # ----------------------------------------------------

            if success:

                print(
                    "\nProcessing completed "
                    "successfully [translate]"
                )

                if debug:

                    print(
                        "Debug mode: Temporary files "
                        "preserved in 'temp' directory "
                        "[translate]"
                    )

            else:

                if (
                    mode in ['batchcheck', 'batch']
                    and status
                ):

                    print(
                        f"\nCurrent batch status: "
                        f"{status.status} "
                        f"[translate]"
                    )

                    if status.status == 'in_progress':

                        print(
                            "Batch processing is still "
                            "in progress [translate]"
                        )

                        print(
                            "Run again with --mode "
                            "batchcheck to monitor "
                            "progress [translate]"
                        )

                    else:

                        print(
                            "\nProcessing failed - "
                            "temporary files preserved "
                            "in 'temp' directory "
                            "[translate]"
                        )

                else:

                    print(
                        "\nProcessing failed - "
                        "temporary files preserved "
                        "in 'temp' directory "
                        "[translate]"
                    )

    # ============================================================
    # PDF
    # ============================================================

    elif filetype == 'pdf':

        success = False

        all_chunks = []
        chapter_map = {}
        translations = {}

        temp_dir = ensure_dir("temp")

        timestamp = datetime.now(
            UTC
        ).strftime(
            '%Y%m%d_%H%M%S'
        )

        job_id = create_job_id(
            input_path,
            from_lang,
            to_lang,
            model
        )

        paths = ensure_temp_structure(
            job_id
        )

        print(
            f"Starting new job: "
            f"{job_id} [translate]"
        )

        print(
            "PDF detected, transcribing... "
            "[translate]"
        )

        if mode == 'batchcheck':

            return

        else:

            # ----------------------------------------------------
            # PDF Handler
            # ----------------------------------------------------

            from app.pipeline.pdf_handler import PDFHandler

            print()
            print("=" * 60)
            print("EPUB INPUT/OUTPUT DEBUG")
            print(f"input_path  : {input_path}")
            print(f"output_path : {output_path}")
            print(f"input exists: {Path(input_path).exists()}")
            print(f"output exists: {Path(output_path).exists()}")
            print("=" * 60)

            all_chunks, chapter_map = (
                PDFHandler.transcribe_pdf(
                    client,
                    input_path,
                    paths,
                    dpi=150,
                    batch=False
                )
            )

            save_chunks(
                paths,
                all_chunks,
                chapter_map
            )

            print(
                f"Transcription of "
                f"{len(all_chunks)} pages complete... "
                f"[translate]"
            )

        translations = {
            chunk_id: chunk
            for chunk_id, chunk in all_chunks
        }

        save_translations(
            paths,
            translations
        )

        print(
            f"Translations saved: "
            f"{paths['translations_file'].name} "
            f"[translate]"
        )

        if mode == 'pdfbilingual':

            PDFHandler.save_bilingual_pdf(
                input_path,
                translations,
                output_path
            )

        else:

            PDFHandler.save_translated_pdf(
                translations,
                output_path
            )

        print(
            f"Finished at: "
            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} "
            f"UTC [translate]"
        )

        success = True

        # FIX:
        # DEBUG -> debug
        keep_temp = debug or not success

        # FIX:
        # DEBUG -> debug
        if not debug:

            file_ids = []

            cleanup_files(
                client,
                file_ids,
                temp_dir=paths['job_dir'],
                keep_temp=keep_temp
            )

        else:

            print(
                f"Preserving temporary files "
                f"(keep_temp={keep_temp}) "
                f"[translate]"
            )