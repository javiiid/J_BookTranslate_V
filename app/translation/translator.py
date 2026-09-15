# ============================================================
# Translation Service
# ============================================================
"""
Central translation service for EPUB/PDF translation.

Responsibilities:
    - Translate individual chunks
    - Validate API responses
    - Clean model output
    - Retry temporary API failures
    - Save progress immediately
    - Resume interrupted translations
    - Manage batch translation workflows
    - Support test translations

Supported modes:
    - fast
    - resume
    - batch
    - batchcheck
    - resumebatch
    - test
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.translation.prompts import get_translation_prompt
from app.glossary.service import load_snapshot, glossary_prompt, check_translation
from app.glossary.automatic import learn_chunk

from app.translation.batch import (
    batch_translate_chunks,
    load_batch_state,
    parse_batch_response,
)

from app.jobs.state import save_translations
from app.jobs.state import deduplicate_chunks

from app.core.paths import ensure_dir

from app.core.retry import (
    retry_operation,
    RetryError,
    get_status_code,
)
from app.core.exceptions import TranslationStopped


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RETRIES = 5

RETRY_BASE_SECONDS = 5.0

RETRY_MAX_SECONDS = 80.0

RETRYABLE_STATUS_CODES = {
    408,  # Request Timeout
    409,  # Conflict / temporary conflict
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}


# ============================================================
# TEST TRANSLATIONS
# ============================================================

def load_test_translations(
    input_path: str | Path,
) -> dict[str, Any] | None:
    """
    Load test translations associated with an input file.

    Expected filename:

        <input_stem>_translations.json

    Example:

        book.epub
        book_translations.json

    Args:
        input_path:
            Original input file.

    Returns:
        Translation dictionary or None if unavailable.
    """

    input_path = Path(input_path)

    test_file = input_path.with_name(
        f"{input_path.stem}_translations.json"
    )

    if not test_file.exists():
        print(
            f"Test translations file not found: "
            f"{test_file} "
            "[load_test_translations]"
        )
        return None

    try:
        with test_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            translations = json.load(file)

    except (OSError, json.JSONDecodeError) as error:

        print(
            f"Error loading test translations: "
            f"{error} "
            "[load_test_translations]"
        )

        return None

    if not isinstance(translations, dict):

        print(
            f"Invalid test translations format: "
            f"{test_file} "
            "[load_test_translations]"
        )

        return None

    translations = _normalize_translations(
        translations
    )

    print(
        f"Loaded {len(translations)} test translations "
        f"from {test_file} "
        "[load_test_translations]"
    )

    return translations


# ============================================================
# TRANSLATION CLEANUP
# ============================================================

def _clean_translation(text: Any) -> str:
    """
    Clean accidental Markdown code fences from model output.

    The translation itself is preserved.

    Examples of unwanted output:

        ```html
        <p>Hello</p>
        ```

    becomes:

        <p>Hello</p>
    """

    if text is None:
        return ""

    cleaned = str(text).strip()

    # --------------------------------------------------------
    # Remove opening code fence
    # --------------------------------------------------------

    cleaned = re.sub(
        r"^```[a-zA-Z0-9_-]*\s*\n",
        "",
        cleaned,
    )

    # --------------------------------------------------------
    # Remove closing code fence
    # --------------------------------------------------------

    cleaned = re.sub(
        r"\n```[\t ]*$",
        "",
        cleaned,
    )

    # --------------------------------------------------------
    # Handle case where model returned only:
    #
    # ```text
    # translation
    # ```
    # --------------------------------------------------------

    if cleaned.startswith("```") and cleaned.endswith("```"):

        lines = cleaned.splitlines()

        if len(lines) >= 2:
            cleaned = "\n".join(
                lines[1:-1]
            )

    return cleaned.strip()


# ============================================================
# API RESPONSE VALIDATION
# ============================================================

def _extract_translation_from_response(
    response: Any,
) -> str:
    """
    Extract translated text from an OpenAI-compatible response.

    Raises:
        RuntimeError:
            If response is missing, malformed, or empty.
    """

    if response is None:
        raise RuntimeError(
            "API returned None response."
        )

    choices = getattr(
        response,
        "choices",
        None,
    )

    if not choices:
        raise RuntimeError(
            "API returned no choices."
        )

    first_choice = choices[0]

    message = getattr(
        first_choice,
        "message",
        None,
    )

    if message is None:
        raise RuntimeError(
            "API response contains no message."
        )

    content = getattr(
        message,
        "content",
        None,
    )

    if content is None:
        raise RuntimeError(
            "API returned empty translation."
        )

    # --------------------------------------------------------
    # Some OpenAI-compatible APIs may return non-string
    # content structures.
    # --------------------------------------------------------

    if isinstance(content, str):

        translated_text = content

    else:

        translated_text = str(content)

    translated_text = translated_text.strip()

    if not translated_text:
        raise RuntimeError(
            "API returned blank translation."
        )

    translated_text = _clean_translation(
        translated_text
    )

    if not translated_text:
        raise RuntimeError(
            "Translation became empty after cleanup."
        )

    return translated_text


# ============================================================
# ERROR HELPERS
# ============================================================

def _print_retry_error(
    chunk_id: Any,
    error: RetryError,
) -> None:
    """
    Print information after all retry attempts fail.
    """

    last_error = getattr(
        error,
        "last_exception",
        None,
    )

    status_code = None

    if last_error is not None:

        status_code = get_status_code(
            last_error
        )

    print("\n" + "=" * 60)

    print("RETRIES EXHAUSTED")

    print(
        f"Chunk       : {chunk_id}"
    )

    print(
        f"Attempts    : {MAX_RETRIES}"
    )

    print(
        f"Status code : {status_code}"
    )

    print(
        f"Last error  : {last_error}"
    )

    print(
        "Already completed chunks are preserved."
    )

    print(
        "Run with --mode resume to continue."
    )

    print("=" * 60)


def _print_api_error(
    chunk_id: Any,
    error: Exception,
) -> None:
    """
    Print information about a non-retryable API error.
    """

    status_code = get_status_code(
        error
    )

    print("\n" + "=" * 60)

    print("NON-RETRYABLE API ERROR")

    print(
        f"Chunk       : {chunk_id}"
    )

    print(
        f"Status code : {status_code}"
    )

    print(
        f"Error       : {error}"
    )

    print("=" * 60)


# ============================================================
# SYSTEM PROMPT
# ============================================================

def _build_system_message(
    from_lang: str,
    to_lang: str,
    filetype: str,
    system_prompt_text: str | None,
) -> str:
    """
    Build the translation system prompt.

    Priority:
        1. Custom system prompt
        2. Default translation system prompt

    Parameters
    ----------
    from_lang:
        Source language.

    to_lang:
        Target language.

    filetype:
        Input file type, such as epub or pdf.

    system_prompt_text:
        Custom system prompt supplied by the caller.
    """

    # ========================================================
    # 1. CUSTOM SYSTEM PROMPT
    # ========================================================

    if system_prompt_text:
        return system_prompt_text

    # ========================================================
    # 2. DEFAULT SYSTEM PROMPT
    # ========================================================

    return f"""
You are a professional literary and technical translator.

Translate the text from {from_lang} to {to_lang}.

The source file is a {filetype.upper()} book.

Translation requirements:

- Preserve the exact meaning of the original text.
- Write natural, fluent, professional Persian.
- Do not translate word-for-word when doing so harms the meaning.
- Preserve the structure of the original text.
- Preserve headings and subheadings.
- Keep technical terminology consistent throughout the book.
- Keep names of models, libraries, APIs, programming languages,
  frameworks, and technical identifiers unchanged.
- Preserve all code exactly as it appears.
- Preserve formulas and mathematical expressions.
- Preserve URLs exactly.
- Preserve numbers and numerical values accurately.
- Do not add explanations, comments, summaries, or opinions.
- Do not omit any part of the source text.
- Do not add information that does not exist in the source.
- Maintain consistency with translations from previous chunks.
- Treat every chunk as part of the same book.
- If a sentence is split across chunks, preserve its meaning and structure.
- Use correct Persian punctuation and half-spaces where appropriate.

Return only the translated text.
""".strip()
# ============================================================
# SINGLE CHUNK TRANSLATION
# ============================================================

def translate_chunk(
    client: Any,
    text: str,
    chunk_id: Any = None,
    from_lang: str = "EN",
    to_lang: str = "FA",
    model: str = "gpt-5.6-terra",
    test_translations: dict[str, Any] | None = None,
    filetype: str = "epub",
    system_prompt_text: str | None = None,
    glossary_snapshot=None,
) -> str:
    """
    Translate one chunk.

    This function performs exactly one API request per
    invocation of api_operation().

    Retry behavior is controlled by retry_operation().
    """

    # ========================================================
    # VALIDATE INPUT
    # ========================================================

    if text is None:

        raise ValueError(
            f"Chunk {chunk_id} contains None text."
        )

    text = str(text)

    if not text.strip():

        raise ValueError(
            f"Chunk {chunk_id} contains empty text."
        )

    # ========================================================
    # TEST MODE
    # ========================================================

    if test_translations is not None:

        translation = test_translations.get(
            str(chunk_id)
        )

        if translation is not None:

            return _clean_translation(
                translation
            )

        print(
            f"Warning: No test translation found "
            f"for chunk {chunk_id} "
            "[translate_chunk]"
        )

        return (
            f"[Translation content for "
            f"chunk-{chunk_id} would go here]"
        )

    # ========================================================
    # BUILD SYSTEM PROMPT
    # ========================================================

    system_message = _build_system_message(
        from_lang=from_lang,
        to_lang=to_lang,
        filetype=filetype,
        system_prompt_text=system_prompt_text,
    )

    system_message = glossary_prompt(system_message, text, glossary_snapshot or {})

    # ========================================================
    # API OPERATION
    # ========================================================

    def api_operation() -> str:
        """
        Execute exactly one API request.
        """

        print(
            f"API request for chunk {chunk_id} "
            "[translate_chunk]"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_message,
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            temperature=0.2,
        )

        return _extract_translation_from_response(
            response
        )

    # ========================================================
    # RETRY
    # ========================================================

    try:

        translated_text = retry_operation(
            operation=api_operation,
            max_attempts=MAX_RETRIES,
            base_delay=RETRY_BASE_SECONDS,
            max_delay=RETRY_MAX_SECONDS,
            retryable_status_codes=tuple(
                RETRYABLE_STATUS_CODES
            ),
        )

        translated_text = _clean_translation(
            translated_text
        )

        if not translated_text:

            raise RuntimeError(
                f"Empty translation returned "
                f"for chunk {chunk_id}."
            )

        print(
            f"✓ Chunk {chunk_id} translated successfully."
        )

        return translated_text

    except KeyboardInterrupt:

        print("\n" + "=" * 60)

        print("CTRL+C DETECTED")

        print(
            f"Translation stopped at chunk {chunk_id}."
        )

        print(
            "Already completed chunks are preserved."
        )

        print(
            "Run with --mode resume to continue."
        )

        print("=" * 60)

        raise

    except RetryError as error:

        _print_retry_error(
            chunk_id=chunk_id,
            error=error,
        )

        raise

    except Exception as error:

        _print_api_error(
            chunk_id=chunk_id,
            error=error,
        )

        raise


# ============================================================
# TRANSLATION DICTIONARY HELPERS
# ============================================================

def _normalize_translations(
    translations: dict[Any, Any] | None,
) -> dict[str, Any]:
    """
    Normalize translation dictionary keys to strings.
    """

    if not translations:

        return {}

    return {
        str(key): value
        for key, value in translations.items()
    }


def _get_untranslated_chunks(
    all_chunks: list[tuple[Any, str]],
    translations: dict[str, Any],
) -> list[tuple[Any, str]]:
    """
    Return chunks that do not have a completed translation.

    Empty translations are also considered incomplete.
    """

    normalized = _normalize_translations(
        translations
    )

    untranslated = []

    for chunk_id, chunk_text in all_chunks:

        key = str(chunk_id)

        existing = normalized.get(
            key
        )

        if existing is None:

            untranslated.append(
                (chunk_id, chunk_text)
            )

            continue

        if not str(existing).strip():

            untranslated.append(
                (chunk_id, chunk_text)
            )

    return untranslated


# ============================================================
# BATCH CHECK
# ============================================================

def _process_batch_check(
    client: Any,
    paths: Any,
) -> tuple[dict[str, Any], Any, Any]:
    """
    Check the current batch status.

    If the batch is completed, retrieve and merge its output.
    """

    temp_dir = ensure_dir(
        "temp"
    )

    state, state_file = load_batch_state(
        temp_dir
    )

    if not state:

        print(
            "No batch state found. "
            "Run with --mode batch first. "
            "[_process_batch_check]"
        )

        return {}, None, None

    batch_id = state.get(
        "batch_id"
    )

    if not batch_id:

        raise RuntimeError(
            "Batch state exists but batch_id is missing."
        )

    print(
        f"Checking status for batch "
        f"{batch_id} "
        "[_process_batch_check]"
    )

    try:

        status = client.batches.retrieve(
            batch_id
        )

    except KeyboardInterrupt:

        print(
            "\nBatch status check interrupted."
        )

        raise

    except Exception as error:

        print(
            f"Failed to retrieve batch status: "
            f"{error}"
        )

        raise

    # ========================================================
    # BATCH NOT COMPLETED
    # ========================================================

    if status.status != "completed":

        print(
            f"Batch status: {status.status} "
            "[_process_batch_check]"
        )

        request_counts = getattr(
            status,
            "request_counts",
            None,
        )

        if request_counts:

            completed = getattr(
                request_counts,
                "completed",
                0,
            )

            total = getattr(
                request_counts,
                "total",
                0,
            )

            print(
                f"Progress: "
                f"{completed}/{total} "
                "[_process_batch_check]"
            )

        return (
            {},
            state.get("input_file_id"),
            status,
        )

    # ========================================================
    # BATCH COMPLETED
    # ========================================================

    print(
        "Batch completed! "
        "Retrieving results... "
        "[_process_batch_check]"
    )

    state_paths = state.get(
        "paths",
        {}
    )

    if not state_paths:

        raise RuntimeError(
            "Batch state does not contain paths."
        )

    batch_paths = {
        key: Path(value)
        for key, value in state_paths.items()
    }

    translations_file = batch_paths.get(
        "translations_file"
    )

    if translations_file is None:

        raise RuntimeError(
            "Batch state does not contain "
            "'translations_file'."
        )

    translations: dict[str, Any] = {}

    # ========================================================
    # LOAD EXISTING TRANSLATIONS
    # ========================================================

    if translations_file.exists():

        print(
            "Loading existing translations..."
        )

        try:

            with translations_file.open(
                "r",
                encoding="utf-8",
            ) as file:

                loaded = json.load(
                    file
                )

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:

            raise RuntimeError(
                f"Failed to load translations file: "
                f"{error}"
            ) from error

        if isinstance(loaded, dict):

            translations = (
                _normalize_translations(
                    loaded
                )
            )

        else:

            raise RuntimeError(
                "Translations file does not contain "
                "a JSON object."
            )

        print(
            f"Loaded {len(translations)} "
            "existing translations."
        )

    # ========================================================
    # OUTPUT FILE
    # ========================================================

    output_file_id = getattr(
        status,
        "output_file_id",
        None,
    )

    if not output_file_id:

        raise RuntimeError(
            "Batch completed but no "
            "output_file_id was returned."
        )

    # ========================================================
    # DOWNLOAD BATCH OUTPUT
    # ========================================================

    print(
        f"Downloading batch output "
        f"{output_file_id}..."
    )

    response = client.files.content(
        output_file_id
    )

    raw_content = response.read()

    if isinstance(raw_content, bytes):

        response_text = raw_content.decode(
            "utf-8"
        )

    else:

        response_text = str(
            raw_content
        )

    if not response_text.strip():

        raise RuntimeError(
            "Batch output file is empty."
        )

    # ========================================================
    # PARSE RESULTS
    # ========================================================

    new_translations = parse_batch_response(
        response_text
    )

    new_translations = (
        _normalize_translations(
            new_translations
        )
    )

    print(
        f"Got {len(new_translations)} "
        "new translations from batch."
    )

    # ========================================================
    # MERGE
    # ========================================================

    translations.update(
        new_translations
    )

    # ========================================================
    # SAVE
    # ========================================================

    save_translations(
        batch_paths,
        translations,
    )

    print(
        f"Total translations after merge: "
        f"{len(translations)}"
    )

    return (
        translations,
        state.get("input_file_id"),
        status,
    )


# ============================================================
# BATCH TRANSLATION
# ============================================================

def _run_batch_translation(
    client: Any,
    chunks: list[tuple[Any, str]],
    translations: dict[str, Any],
    from_lang: str,
    to_lang: str,
    mode: str,
    model: str,
    test_translations: dict[str, Any] | None,
    debug: bool,
    paths: Any,
    chapter_map: Any,
    filetype: str,
) -> tuple[dict[str, Any], Any, Any]:
    """
    Start or resume a batch translation.

    Only untranslated chunks are sent to the batch layer.
    """

    if not chunks:

        print(
            "No untranslated chunks found."
        )

        return (
            translations,
            None,
            None,
        )

    print(
        f"Translating {len(chunks)} chunks "
        f"in '{mode}' mode "
        "[_run_batch_translation]"
    )

    (
        new_translations,
        input_file_id,
        status,
    ) = batch_translate_chunks(
        client,
        chunks,
        from_lang,
        to_lang,
        mode=mode,
        model=model,
        test_translations=test_translations,
        keep_temp=debug,
        paths=paths,
        chapter_map=chapter_map,
        filetype=filetype,
    )

    new_translations = (
        _normalize_translations(
            new_translations
        )
    )

    translations.update(
        new_translations
    )

    save_translations(
        paths,
        translations,
    )

    return (
        translations,
        input_file_id,
        status,
    )


# ============================================================
# FAST / RESUME
# ============================================================

def _process_fast_resume(
    client: Any,
    all_chunks: list[tuple[Any, str]],
    translations: dict[str, Any],
    mode: str,
    from_lang: str,
    to_lang: str,
    paths: Any,
    model: str,
    test_translations: dict[str, Any] | None,
    filetype: str,
    system_prompt_text: str | None,
    stop_event: Any = None,
) -> tuple[dict[str, Any], None, None]:
    """
    Process chunks sequentially.

    Every successful translation is saved immediately.

    This is what makes resume functionality reliable.
    """

    total_chunks = len(
        all_chunks
    )

    translations = _normalize_translations(
        translations
    )

    untranslated_chunks = (
        _get_untranslated_chunks(
            all_chunks,
            translations,
        )
    )

    untranslated_count = len(
        untranslated_chunks
    )

    completed_count = (
        total_chunks
        - untranslated_count
    )

    # ========================================================
    # STATUS
    # ========================================================

    print(
        f"Total chunks: {total_chunks}"
    )

    print(
        f"Already completed: "
        f"{completed_count}"
    )

    print(
        f"Remaining: "
        f"{untranslated_count}"
    )

    # ========================================================
    # EVERYTHING COMPLETE
    # ========================================================

    if test_translations is None and load_snapshot(paths).get('auto_extract'):
        for completed_id, completed_source in all_chunks:
            if stop_event is not None and stop_event.is_set():
                raise TranslationStopped
            if str(completed_id) in translations:
                learn_chunk(client, paths, completed_id, completed_source,
                            translations[str(completed_id)], model, stop_event)

    if untranslated_count == 0:

        print("\n" + "=" * 60)

        print(
            "ALL TRANSLATIONS ALREADY COMPLETED"
        )

        print(
            f"Total translations: "
            f"{len(translations)}/{total_chunks}"
        )

        print("=" * 60)

        return (
            translations,
            None,
            None,
        )

    # ========================================================
    # START
    # ========================================================

    print(
        f"Translating {untranslated_count} "
        f"chunks in '{mode}' mode "
        "[_process_fast_resume]"
    )

    # ========================================================
    # CHUNK LOOP
    # ========================================================

    for position, (
        chunk_id,
        chunk_text,
    ) in enumerate(
        untranslated_chunks,
        start=1,
    ):

        # Let an in-flight request finish and save, then stop before the
        # following chunk. This keeps a web-stopped job safely resumable.
        if stop_event is not None and stop_event.is_set():
            print("Stop requested. Completed translations are preserved.")
            raise TranslationStopped

        current_number = (
            completed_count
            + position
        )

        print("\n" + "=" * 60)

        print(
            f"Translating chunk "
            f"{current_number}/{total_chunks}"
        )

        print(
            f"Chunk ID: {chunk_id}"
        )

        print(
            f"Completed: "
            f"{len(translations)}/{total_chunks}"
        )

        print("=" * 60)

        try:

            glossary_snapshot = load_snapshot(paths)
            translated_text = translate_chunk(
                client=client,
                text=chunk_text,
                chunk_id=chunk_id,
                from_lang=from_lang,
                to_lang=to_lang,
                model=model,
                test_translations=test_translations,
                filetype=filetype,
                system_prompt_text=system_prompt_text,
                glossary_snapshot=glossary_snapshot,
            )

            # ------------------------------------------------
            # VALIDATE BEFORE SAVE
            # ------------------------------------------------

            translated_text = _clean_translation(
                translated_text
            )
            for term in check_translation(chunk_text, translated_text, glossary_snapshot):
                print(f"Glossary review needed in chunk {chunk_id}: {term['source_term']} -> {term['target_term']}")

            if not translated_text:

                raise RuntimeError(
                    f"Chunk {chunk_id} "
                    "returned empty translation."
                )

            # ------------------------------------------------
            # SAVE IMMEDIATELY
            # ------------------------------------------------

            translations[
                str(chunk_id)
            ] = translated_text

            save_translations(
                paths,
                translations,
            )

            if test_translations is None:
                learn_chunk(client, paths, chunk_id, chunk_text, translated_text, model, stop_event)

            print(
                f"✓ Chunk {chunk_id} "
                "translated successfully."
            )

            print(
                f"✓ Progress saved: "
                f"{len(translations)}/{total_chunks}"
            )

        except KeyboardInterrupt:

            print("\n" + "=" * 60)

            print(
                "TRANSLATION INTERRUPTED"
            )

            print(
                f"Completed: "
                f"{len(translations)}/{total_chunks}"
            )

            print(
                "All completed translations "
                "have been saved."
            )

            print(
                "Run with --mode resume "
                "to continue."
            )

            print("=" * 60)

            raise

        except Exception as error:

            print("\n" + "=" * 60)

            print(
                f"ERROR translating chunk "
                f"{chunk_id}"
            )

            print(
                f"Error: {error}"
            )

            print(
                f"Completed translations: "
                f"{len(translations)}/{total_chunks}"
            )

            print(
                "Completed translations "
                "have been saved."
            )

            print(
                "Run with --mode resume "
                "to continue."
            )

            print("=" * 60)

            raise

    # ========================================================
    # COMPLETE
    # ========================================================

    print("\n" + "=" * 60)

    print(
        "ALL TRANSLATIONS COMPLETED"
    )

    print(
        f"Total translations: "
        f"{len(translations)}/{total_chunks}"
    )

    print("=" * 60)

    return (
        translations,
        None,
        None,
    )


# ============================================================
# TEST MODE
# ============================================================

def _process_test_mode(
    untranslated_chunks: list[tuple[Any, str]],
    translations: dict[str, Any],
    test_translations: dict[str, Any] | None,
    paths: Any,
) -> tuple[dict[str, Any], None, None]:
    """
    Process translation using local test translations.

    No API request is made.
    """

    if not test_translations:

        print(
            "Error: test_translations not provided "
            "[_process_test_mode]"
        )

        return (
            translations,
            None,
            None,
        )

    test_translations = (
        _normalize_translations(
            test_translations
        )
    )

    translations = _normalize_translations(
        translations
    )

    for chunk_id, _ in untranslated_chunks:

        chunk_key = str(
            chunk_id
        )

        if chunk_key in test_translations:

            translation = _clean_translation(
                test_translations[
                    chunk_key
                ]
            )

            if translation:

                translations[
                    chunk_key
                ] = translation

                continue

        print(
            f"Warning: No valid test translation "
            f"found for chunk {chunk_id} "
            "[_process_test_mode]"
        )

        translations[
            chunk_key
        ] = (
            f"[TEST MODE] No translation "
            f"for chunk: {chunk_id}"
        )

    save_translations(
        paths,
        translations,
    )

    print(
        f"Test mode completed. "
        f"Translations: {len(translations)}"
    )

    return (
        translations,
        None,
        None,
    )


# ============================================================
# MAIN TRANSLATION PROCESSOR
# ============================================================

def process_translations(
    client: Any,
    all_chunks: list[tuple[Any, str]],
    translations: dict[str, Any],
    mode: str,
    from_lang: str,
    to_lang: str,
    paths: Any,
    model: str = "gpt-5.6-terra",
    test_translations: dict[str, Any] | None = None,
    debug: bool = False,
    chapter_map: Any = None,
    filetype: str = "epub",
    translation_prompt=None,
    system_prompt_text: str | None = None,
    stop_event: Any = None,
) -> tuple[dict[str, Any], Any, Any]:
    """
    Main translation workflow dispatcher.

    Supported modes:

        fast
        resume
        batch
        batchcheck
        resumebatch
        test

    Behavior:

        fast:
            Translate missing chunks sequentially.

        resume:
            Same behavior as fast, but intended for
            continuing a previously interrupted job.

        batch:
            Send missing chunks to batch API.

        resumebatch:
            Continue using batch workflow.

        batchcheck:
            Check current batch status and retrieve
            results if completed.

        test:
            Use local test translations without API calls.
    """

    # ========================================================
    # VALIDATE MODE
    # ========================================================

    supported_modes = {
        "fast",
        "resume",
        "batch",
        "batchcheck",
        "resumebatch",
        "test",
    }

    if mode not in supported_modes:

        raise ValueError(
            f"Unknown translation mode: {mode}. "
            f"Supported modes: "
            f"{', '.join(sorted(supported_modes))}"
        )

    # ========================================================
    # NORMALIZE TRANSLATIONS
    # ========================================================

    translations = _normalize_translations(
        translations
    )

    # ========================================================
    # NORMALIZE CHUNKS
    # ========================================================

    if all_chunks is None:

        all_chunks = []

    # A malformed source or repeated reconstruction entry must not cause the
    # same chunk ID to be sent to the provider more than once.
    all_chunks = deduplicate_chunks(all_chunks)

    # ========================================================
    # BATCH CHECK
    # ========================================================

    if mode == "batchcheck":

        return _process_batch_check(
            client=client,
            paths=paths,
        )

    # ========================================================
    # FIND UNTRANSLATED CHUNKS
    # ========================================================

    untranslated_chunks = (
        _get_untranslated_chunks(
            all_chunks,
            translations,
        )
    )

    # ========================================================
    # FAST / RESUME
    # ========================================================

    if mode in {
        "fast",
        "resume",
    }:

        return _process_fast_resume(
            client=client,
            all_chunks=all_chunks,
            translations=translations,
            mode=mode,
            from_lang=from_lang,
            to_lang=to_lang,
            paths=paths,
            model=model,
            test_translations=test_translations,
            filetype=filetype,
            system_prompt_text=system_prompt_text,
            stop_event=stop_event,
        )

    # ========================================================
    # BATCH / RESUME BATCH
    # ========================================================

    if mode in {
        "batch",
        "resumebatch",
    }:

        return _run_batch_translation(
            client=client,
            chunks=untranslated_chunks,
            translations=translations,
            from_lang=from_lang,
            to_lang=to_lang,
            mode="batch",
            model=model,
            test_translations=test_translations,
            debug=debug,
            paths=paths,
            chapter_map=chapter_map,
            filetype=filetype,
        )

    # ========================================================
    # TEST
    # ========================================================

    if mode == "test":

        return _process_test_mode(
            untranslated_chunks=untranslated_chunks,
            translations=translations,
            test_translations=test_translations,
            paths=paths,
        )

    # ========================================================
    # SAFETY FALLBACK
    # ========================================================

    raise RuntimeError(
        f"Unhandled translation mode: {mode}"
    )
