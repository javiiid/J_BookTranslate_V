# ============================================================
# Translation Service
# ============================================================

import json
import re
from pathlib import Path

from app.translation.prompts import system_prompt

from app.jobs.state import save_translations

from app.translation.batch import (
    batch_translate_chunks,
    load_batch_state,
    parse_batch_response,
)

from app.core.paths import ensure_dir

from app.core.retry import (
    retry_operation,
    RetryError,
    get_status_code,
)


# ============================================================
# API RETRY CONFIG
# ============================================================

MAX_RETRIES = 5

RETRY_BASE_SECONDS = 5.0

RETRY_MAX_SECONDS = 80.0

RETRYABLE_STATUS_CODES = {
    408,  # Request Timeout
    429,  # Rate Limit
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}


# ============================================================
# LOAD TEST TRANSLATIONS
# ============================================================

def load_test_translations(input_path):
    """
    Load test translations from:

        <input_stem>_translations.json

    Returns:
        dict | None
    """

    input_path = Path(input_path)

    test_file = input_path.with_name(
        f"{input_path.stem}_translations.json"
    )

    if not test_file.exists():
        print(
            f"Test translations file not found: "
            f"{test_file} [load_test_translations]"
        )
        return None

    try:
        with open(
            test_file,
            "r",
            encoding="utf-8",
        ) as f:
            translations = json.load(f)

        print(
            f"Loaded {len(translations)} test translations "
            f"from {test_file} [load_test_translations]"
        )

        return translations

    except Exception as e:
        print(
            f"Error loading test translations: {e} "
            f"[load_test_translations]"
        )
        return None


# ============================================================
# CLEAN TRANSLATED RESPONSE
# ============================================================

def _clean_translation(text):
    """
    Remove accidental Markdown code fences from
    the model response.

    The actual translation content is preserved.
    """

    if text is None:
        return ""

    text = str(text).strip()

    # Remove opening code fence.
    #
    # Example:
    #
    # ```html
    # <html>...</html>
    #
    text = re.sub(
        r"^```[a-zA-Z0-9_-]*\s*\n",
        "",
        text,
    )

    # Remove closing code fence.
    #
    # Example:
    #
    # </html>
    # ```
    #
    text = re.sub(
        r"\n```\s*$",
        "",
        text,
    )

    return text.strip()


# ============================================================
# VALIDATE API RESPONSE
# ============================================================

def _extract_translation_from_response(response):
    """
    Validate an OpenAI-compatible API response.

    Returns:
        str:
            Clean translated text.

    Raises:
        RuntimeError:
            If the API response is malformed or empty.
    """

    # --------------------------------------------------------
    # Response object
    # --------------------------------------------------------

    if response is None:
        raise RuntimeError(
            "API returned None response."
        )

    # --------------------------------------------------------
    # Choices
    # --------------------------------------------------------

    choices = getattr(
        response,
        "choices",
        None,
    )

    if not choices:
        raise RuntimeError(
            "API returned no choices."
        )

    # --------------------------------------------------------
    # First choice
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Message content
    # --------------------------------------------------------

    translated_text = getattr(
        message,
        "content",
        None,
    )

    if translated_text is None:
        raise RuntimeError(
            "API returned empty translation."
        )

    translated_text = str(
        translated_text
    ).strip()

    if not translated_text:
        raise RuntimeError(
            "API returned blank translation."
        )

    # --------------------------------------------------------
    # Clean model output
    # --------------------------------------------------------

    translated_text = _clean_translation(
        translated_text
    )

    if not translated_text:
        raise RuntimeError(
            "Translation became empty after cleanup."
        )

    return translated_text


# ============================================================
# TRANSLATE SINGLE CHUNK
# ============================================================

def translate_chunk(
    client,
    text,
    chunk_id=None,
    from_lang="EN",
    to_lang="FA",
    model="gpt-5.6-terra",
    test_translations=None,
    filetype="epub",
):
    """
    Translate one chunk.

    Features:
        - Test mode
        - Centralized retry system
        - Exponential backoff
        - Retryable HTTP errors
        - Ctrl+C support
        - OpenAI-compatible APIs
        - Immediate failure for permanent errors
        - Response validation
        - Translation cleanup

    Retry logic is intentionally delegated to:

        app.core.retry.retry_operation()

    This function performs one API operation and lets
    retry_operation() decide whether it should be repeated.
    """

    # ========================================================
    # TEST MODE
    # ========================================================

    if test_translations is not None:

        translation = test_translations.get(
            str(chunk_id)
        )

        if translation:
            return translation

        print(
            f"Warning: No test translation found for "
            f"chunk {chunk_id} [translate_chunk]"
        )

        return (
            f"[Translation content for "
            f"chunk-{chunk_id} would go here]"
        )

    # ========================================================
    # BUILD SYSTEM PROMPT
    # ========================================================

    system_message = system_prompt(
        from_lang,
        to_lang,
        filetype,
    )

    user_message = text

    # ========================================================
    # SINGLE API OPERATION
    # ========================================================

    def api_operation():
        """
        Perform exactly one API request.

        retry_operation() is responsible for retrying
        this function when a retryable error occurs.
        """

        print(
            f"API request for chunk {chunk_id} "
            f"[translate_chunk]"
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
                    "content": user_message,
                },
            ],
            temperature=0.2,
        )

        return _extract_translation_from_response(
            response
        )

    # ========================================================
    # EXECUTE API OPERATION WITH RETRY
    # ========================================================

    try:

        translated_text = retry_operation(
            operation=api_operation,
            max_attempts=MAX_RETRIES,
            base_delay=RETRY_BASE_SECONDS,
            max_delay=RETRY_MAX_SECONDS,
            retryable_status_codes=(
                RETRYABLE_STATUS_CODES
            ),
        )

        print(
            f"✓ Chunk {chunk_id} translated successfully."
        )

        return translated_text

    # ========================================================
    # CTRL+C
    # ========================================================

    except KeyboardInterrupt:

        print(
            "\n"
            + "=" * 60
        )

        print(
            "CTRL+C DETECTED"
        )

        print(
            f"Translation stopped at chunk "
            f"{chunk_id}."
        )

        print(
            "Already completed chunks are preserved."
        )

        print(
            "Run with --mode resume to continue."
        )

        print(
            "=" * 60
        )

        raise

    # ========================================================
    # RETRIES EXHAUSTED
    # ========================================================

    except RetryError as e:

        last_error = e.last_exception

        status_code = None

        if last_error is not None:
            status_code = get_status_code(
                last_error
            )

        print(
            "\n"
            + "=" * 60
        )

        print(
            "RETRIES EXHAUSTED"
        )

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

        print(
            "=" * 60
        )

        raise

    # ========================================================
    # OTHER ERROR
    # ========================================================

    except Exception as e:

        status_code = get_status_code(
            e
        )

        print(
            "\n"
            + "=" * 60
        )

        print(
            "NON-RETRYABLE API ERROR"
        )

        print(
            f"Chunk       : {chunk_id}"
        )

        print(
            f"Status code : {status_code}"
        )

        print(
            f"Error       : {e}"
        )

        print(
            "=" * 60
        )

        raise


# ============================================================
# PROCESS TRANSLATIONS
# ============================================================

def process_translations(
    client,
    all_chunks,
    translations,
    mode,
    from_lang,
    to_lang,
    paths,
    model="gpt-5.6-terra",
    test_translations=None,
    debug=False,
    chapter_map=None,
    filetype="epub",
):
    """
    Process translations according to the selected mode.

    Every successfully translated chunk is saved immediately.

    This makes resume possible after:

        - Ctrl+C
        - API errors
        - Retry exhaustion
        - Connection errors
        - Application crashes

    Supported modes:

        fast
        resume
        batch
        batchcheck
        resumebatch
        test
    """

    # ========================================================
    # BATCH CHECK
    # ========================================================

    if mode == "batchcheck":

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
                "[process_translations]"
            )

            return {}, None, None

        batch_id = state["batch_id"]

        print(
            f"Checking status for batch "
            f"{batch_id} [process_translations]"
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

        # ----------------------------------------------------
        # Batch still running
        # ----------------------------------------------------

        if status.status != "completed":

            print(
                f"Batch status: {status.status} "
                f"[process_translations]"
            )

            request_counts = getattr(
                status,
                "request_counts",
                None,
            )

            if request_counts:

                print(
                    f"Progress: "
                    f"{request_counts.completed}/"
                    f"{request_counts.total} "
                    f"[process_translations]"
                )

            return (
                {},
                state["input_file_id"],
                status,
            )

        # ----------------------------------------------------
        # Batch completed
        # ----------------------------------------------------

        print(
            "Batch completed! Retrieving results... "
            "[process_translations]"
        )

        paths = {
            k: Path(v)
            for k, v in state["paths"].items()
        }

        translations = {}

        # ----------------------------------------------------
        # Load existing translations
        # ----------------------------------------------------

        translations_file = Path(
            paths["translations_file"]
        )

        if translations_file.exists():

            print(
                "Loading existing translations... "
                "[process_translations]"
            )

            with open(
                translations_file,
                "r",
                encoding="utf-8",
            ) as f:

                translations = json.load(
                    f
                )

            print(
                f"Loaded {len(translations)} existing "
                f"translations [process_translations]"
            )

        # ----------------------------------------------------
        # Retrieve batch output
        # ----------------------------------------------------

        response = client.files.content(
            status.output_file_id
        )

        response_text = (
            response
            .read()
            .decode("utf-8")
        )

        new_translations = parse_batch_response(
            response_text
        )

        print(
            f"Got {len(new_translations)} new translations "
            f"from batch [process_translations]"
        )

        translations.update(
            new_translations
        )

        save_translations(
            paths,
            translations,
        )

        print(
            f"Total translations after merge: "
            f"{len(translations)} "
            f"[process_translations]"
        )

        return (
            translations,
            state["input_file_id"],
            status,
        )

    # ========================================================
    # NORMALIZE TRANSLATIONS
    # ========================================================

    translations = {
        str(k): v
        for k, v in translations.items()
    }

    # ========================================================
    # FIND UNTRANSLATED CHUNKS
    # ========================================================

    untranslated_chunks = [
        (
            chunk_id,
            chunk_text,
        )
        for chunk_id, chunk_text in all_chunks
        if str(chunk_id) not in translations
    ]

    # ========================================================
    # RESUME BATCH
    # ========================================================

    if mode == "resumebatch":

        print(
            f"\nResuming batch translation for "
            f"{len(untranslated_chunks)} remaining chunks "
            f"[process_translations]"
        )

        if not untranslated_chunks:

            print(
                "No untranslated chunks found - "
                "all translations complete! "
                "[process_translations]"
            )

            return (
                translations,
                None,
                None,
            )

        new_translations, input_file_id, status = (
            batch_translate_chunks(
                client,
                untranslated_chunks,
                from_lang,
                to_lang,
                mode="batch",
                model=model,
                test_translations=test_translations,
                keep_temp=debug,
                paths=paths,
                chapter_map=chapter_map,
                filetype=filetype,
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

    # ========================================================
    # FAST / RESUME
    # ========================================================

    if mode in (
        "fast",
        "resume",
    ):

        total_chunks = len(
            all_chunks
        )

        untranslated_count = len(
            untranslated_chunks
        )

        skipped_count = (
            total_chunks
            - untranslated_count
        )

        if skipped_count > 0:

            print(
                f"Skipping already translated "
                f"{skipped_count} chunks "
                f"[process_translations]"
            )

        # ----------------------------------------------------
        # Nothing left to translate
        # ----------------------------------------------------

        if untranslated_count == 0:

            print(
                "\n"
                + "=" * 60
            )

            print(
                "ALL TRANSLATIONS ALREADY COMPLETED"
            )

            print(
                f"Total translations: "
                f"{len(translations)}/{total_chunks}"
            )

            print(
                "=" * 60
            )

            return (
                translations,
                None,
                None,
            )

        print(
            f"Translating {untranslated_count} chunks "
            f"in '{mode}' mode "
            f"[process_translations]"
        )

        # ====================================================
        # CHUNK LOOP
        # ====================================================

        for position, (
            chunk_id,
            chunk_text,
        ) in enumerate(
            untranslated_chunks,
            start=1,
        ):

            current_number = (
                skipped_count
                + position
            )

            print(
                "\n"
                + "=" * 60
            )

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

            print(
                "=" * 60
            )

            try:

                # ------------------------------------------------
                # Translate chunk
                # ------------------------------------------------

                translated_text = translate_chunk(
                    client,
                    chunk_text,
                    chunk_id=chunk_id,
                    from_lang=from_lang,
                    to_lang=to_lang,
                    model=model,
                    test_translations=test_translations,
                    filetype=filetype,
                )

                # ------------------------------------------------
                # Save immediately
                # ------------------------------------------------

                translations[
                    str(chunk_id)
                ] = translated_text

                save_translations(
                    paths,
                    translations,
                )

                print(
                    f"✓ Chunk {chunk_id} translated successfully."
                )

                print(
                    f"✓ Progress saved: "
                    f"{len(translations)}/{total_chunks}"
                )

            # ====================================================
            # CTRL+C
            # ====================================================

            except KeyboardInterrupt:

                print(
                    "\n"
                    + "=" * 60
                )

                print(
                    "TRANSLATION INTERRUPTED"
                )

                print(
                    f"Completed: "
                    f"{len(translations)}/{total_chunks}"
                )

                print(
                    "All completed translations have been saved."
                )

                print(
                    "Run the same command with:"
                )

                print(
                    "--mode resume"
                )

                print(
                    "to continue from the last completed chunk."
                )

                print(
                    "=" * 60
                )

                raise

            # ====================================================
            # OTHER ERROR
            # ====================================================

            except Exception as e:

                print(
                    "\n"
                    + "=" * 60
                )

                print(
                    f"ERROR translating chunk {chunk_id}"
                )

                print(
                    f"Error: {e}"
                )

                print(
                    f"Completed translations: "
                    f"{len(translations)}/{total_chunks}"
                )

                print(
                    "Completed translations have been saved."
                )

                print(
                    "You can continue later with:"
                )

                print(
                    "--mode resume"
                )

                print(
                    "=" * 60
                )

                raise

        # ====================================================
        # ALL COMPLETE
        # ====================================================

        print(
            "\n"
            + "=" * 60
        )

        print(
            "ALL TRANSLATIONS COMPLETED"
        )

        print(
            f"Total translations: "
            f"{len(translations)}/{total_chunks}"
        )

        print(
            "=" * 60
        )

        return (
            translations,
            None,
            None,
        )

    # ========================================================
    # BATCH MODE
    # ========================================================

    if mode == "batch":

        print(
            f"Translating "
            f"{len(untranslated_chunks)} chunks "
            f"in 'batch' mode "
            f"[process_translations]"
        )

        new_translations, input_file_id, status = (
            batch_translate_chunks(
                client,
                untranslated_chunks,
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

    # ========================================================
    # TEST MODE
    # ========================================================

    if mode == "test":

        if test_translations:

            for chunk_id, _ in untranslated_chunks:

                if str(chunk_id) in test_translations:

                    translations[
                        str(chunk_id)
                    ] = test_translations[
                        str(chunk_id)
                    ]

                else:

                    print(
                        f"Warning: No test translation "
                        f"found for chunk {chunk_id} "
                        f"[process_translations]"
                    )

                    translations[
                        str(chunk_id)
                    ] = (
                        f"[TEST MODE] No translation "
                        f"for chunk: {chunk_id}"
                    )

            save_translations(
                paths,
                translations,
            )

        else:

            print(
                "Error: test_translations not provided "
                "[process_translations]"
            )

        return (
            translations,
            None,
            None,
        )

    # ========================================================
    # UNKNOWN MODE
    # ========================================================

    print(
        f"Unknown mode: {mode} "
        f"[process_translations]"
    )

    return (
        translations,
        None,
        None,
    )