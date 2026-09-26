
# ============================================================
# Ctrl+C -> Save Progress -> Resume Test
# ============================================================

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import app.translation.translator as translator_module
from app.translation.translator import process_translations
import app.core.retry as retry_module


class _PinnedConcurrency:
    """Pin the worker count and disable pacing for the duration of a test.

    These tests assert *resume semantics* - nothing is falsely marked complete,
    and a later run picks up where the interrupted one stopped. Those properties
    do not depend on how many chunks may be in flight, but the number of API
    calls made before an interrupt does. Reading the ceiling from
    config/config.yaml made the suite change behaviour when that file changed,
    so the environment is pinned here instead.
    """

    def __init__(self, workers=1):
        self.workers = workers
        self._mode = None
        self._workers = None
        self._limiter = None

    def __enter__(self):
        self._workers = translator_module._translation_concurrency
        self._limiter = translator_module._build_rate_limiter
        translator_module._translation_concurrency = lambda: self.workers
        translator_module._build_rate_limiter = lambda concurrency: None
        return self

    def __exit__(self, *exc):
        translator_module._translation_concurrency = self._workers
        translator_module._build_rate_limiter = self._limiter
        return False


# ============================================================
# FAKE API ERROR
# ============================================================

class FakeAPIError(Exception):
    """
    Fake HTTP error used to simulate a temporary API failure.
    """

    def __init__(
        self,
        message="Service Unavailable",
        status_code=503,
    ):
        super().__init__(message)
        self.status_code = status_code


# ============================================================
# FAKE API CLIENT
# ============================================================

class FakeCompletions:
    """
    Fake OpenAI-compatible chat completion client.

    Behaviour:

        chunk-0 -> success
        chunk-1 -> success
        chunk-2 -> first request fails with 503,
                   second request succeeds
        chunk-3 -> success

    Phase 1:
        Ctrl+C is simulated during the retry wait for chunk-2.

    Phase 2:
        A new client is created and translation resumes.

        chunk-0 and chunk-1 are skipped.
        chunk-2 is processed again.
        Its first request fails with 503.
        Retry performs the second request successfully.
        chunk-3 then succeeds.
    """

    def __init__(self):
        self.calls = []
        self.chunk_attempts = {}

    def create(
        self,
        model,
        messages,
        temperature=0.2,
        **kwargs,
    ):
        chunk_id = messages[1]["content"]

        self.calls.append(chunk_id)

        attempt = (
            self.chunk_attempts.get(
                chunk_id,
                0,
            )
            + 1
        )

        self.chunk_attempts[chunk_id] = attempt

        print(
            f"Fake API call #{len(self.calls)} "
            f"for {chunk_id}"
        )

        # ----------------------------------------------------
        # chunk-2:
        # first API request -> HTTP 503
        # second API request -> success
        # ----------------------------------------------------

        if (
            chunk_id == "chunk-2"
            and attempt == 1
        ):
            print(
                "Simulating HTTP 503..."
            )

            raise FakeAPIError(
                status_code=503
            )

        # ----------------------------------------------------
        # Successful response.
        # ----------------------------------------------------

        class FakeMessage:
            content = (
                f"Translated {chunk_id}"
            )

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [
                FakeChoice()
            ]

        return FakeResponse()


# ============================================================
# FAKE CHAT
# ============================================================

class FakeChat:

    def __init__(self):
        self.completions = FakeCompletions()


# ============================================================
# FAKE CLIENT
# ============================================================

class FakeClient:

    def __init__(self):
        self.chat = FakeChat()


# ============================================================
# TEST PATHS
# ============================================================

def create_test_paths(temp_dir):
    """
    Create the minimum path structure required
    by process_translations().
    """

    temp_dir = Path(temp_dir)

    translations_file = (
        temp_dir / "translations.json"
    )

    return {
        "translations_file": translations_file,
    }


# ============================================================
# LOAD TRANSLATIONS
# ============================================================

def load_translations(translations_file):
    """
    Load translations.json.

    Returns:
        dict
    """

    translations_file = Path(
        translations_file
    )

    if not translations_file.exists():
        return {}

    with open(
        translations_file,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ============================================================
# TEST
# ============================================================

def test_ctrl_c_save_and_resume():

    print()
    print("=" * 60)
    print(
        "CTRL+C -> SAVE PROGRESS -> RESUME TEST"
    )
    print("=" * 60)

    with TemporaryDirectory() as temp_dir:

        # ====================================================
        # PATHS
        # ====================================================

        paths = create_test_paths(
            temp_dir
        )

        # ====================================================
        # TEST CHUNKS
        # ====================================================

        all_chunks = [
            ("chunk-0", "chunk-0"),
            ("chunk-1", "chunk-1"),
            ("chunk-2", "chunk-2"),
            ("chunk-3", "chunk-3"),
        ]

        translations = {}

        # ====================================================
        # PHASE 1
        # ====================================================

        print()
        print("=" * 60)
        print(
            "PHASE 1: TRANSLATE UNTIL CTRL+C"
        )
        print("=" * 60)

        client = FakeClient()

        # ----------------------------------------------------
        # Save original retry sleep.
        # ----------------------------------------------------

        original_sleep = (
            retry_module.interruptible_sleep
        )

        interrupted = {
            "value": False
        }

        # ----------------------------------------------------
        # Fake retry sleep.
        #
        # Instead of actually waiting 5 seconds,
        # simulate Ctrl+C immediately.
        # ----------------------------------------------------

        def fake_interruptible_sleep(
            seconds,
            stop_event=None,
        ):

            print()
            print(
                f"[TEST] Retry waiting for "
                f"{seconds:g}s..."
            )

            if not interrupted["value"]:

                interrupted["value"] = True

                print(
                    "[TEST] Simulating Ctrl+C..."
                )

                raise KeyboardInterrupt

        # ----------------------------------------------------
        # Patch centralized retry utility.
        # ----------------------------------------------------

        retry_module.interruptible_sleep = (
            fake_interruptible_sleep
        )

        # ====================================================
        # RUN PHASE 1
        # ====================================================

        try:

            with _PinnedConcurrency(workers=1):

                process_translations(
                    client=client,
                    all_chunks=all_chunks,
                    translations=translations,
                    mode="fast",
                    from_lang="EN",
                    to_lang="FA",
                    paths=paths,
                    model="gpt-5.6-terra",
                )

        except KeyboardInterrupt:

            print()
            print(
                "✓ KeyboardInterrupt received."
            )

        finally:

            # ------------------------------------------------
            # ALWAYS restore original function.
            # ------------------------------------------------

            retry_module.interruptible_sleep = (
                original_sleep
            )

        # ====================================================
        # VALIDATE SAVED PROGRESS
        # ====================================================

        saved = load_translations(
            paths["translations_file"]
        )

        print()
        print(
            f"Saved translations: "
            f"{len(saved)}"
        )

        # ----------------------------------------------------
        # chunk-0
        # ----------------------------------------------------

        assert (
            "chunk-0" in saved
        )

        print(
            "✓ chunk-0 preserved."
        )

        # ----------------------------------------------------
        # chunk-1
        # ----------------------------------------------------

        assert (
            "chunk-1" in saved
        )

        print(
            "✓ chunk-1 preserved."
        )

        # ----------------------------------------------------
        # chunk-2 must NOT exist.
        # ----------------------------------------------------

        assert (
            "chunk-2" not in saved
        )

        print(
            "✓ chunk-2 was not falsely marked complete."
        )

        # ----------------------------------------------------
        # chunk-3 must NOT exist.
        # ----------------------------------------------------

        assert (
            "chunk-3" not in saved
        )

        print(
            "✓ chunk-3 was not processed."
        )

        # ====================================================
        # VERIFY PHASE 1 API CALLS
        # ====================================================

        phase1_calls = (
            client
            .chat
            .completions
            .calls
        )

        assert (
            len(phase1_calls) == 3
            and set(phase1_calls) == {"chunk-0", "chunk-1", "chunk-2"}
        )

        print(
            "✓ No API request was made after Ctrl+C."
        )

        print(
            "✓ Progress correctly saved."
        )

        # ====================================================
        # PHASE 2
        # ====================================================

        print()
        print("=" * 60)
        print(
            "PHASE 2: RESUME"
        )
        print("=" * 60)

        # ----------------------------------------------------
        # Simulate a new application process.
        # ----------------------------------------------------

        resume_client = FakeClient()

        resumed_translations = (
            load_translations(
                paths["translations_file"]
            )
        )

        print(
            f"Loaded existing translations: "
            f"{len(resumed_translations)}"
        )

        # ====================================================
        # RESUME TRANSLATION
        # ====================================================

        with _PinnedConcurrency(workers=1):

            process_translations(
                client=resume_client,
                all_chunks=all_chunks,
                translations=resumed_translations,
                mode="resume",
                from_lang="EN",
                to_lang="FA",
                paths=paths,
                model="gpt-5.6-terra",
            )

        # ====================================================
        # VALIDATE FINAL STATE
        # ====================================================

        final_translations = (
            load_translations(
                paths["translations_file"]
            )
        )

        print()
        print(
            f"Final translations: "
            f"{len(final_translations)}/4"
        )

        # ----------------------------------------------------
        # All four chunks must exist.
        # ----------------------------------------------------

        assert (
            set(final_translations.keys())
            == {
                "chunk-0",
                "chunk-1",
                "chunk-2",
                "chunk-3",
            }
        )

        print(
            "✓ All 4 chunks translated."
        )

        # ====================================================
        # VERIFY TRANSLATION CONTENT
        # ====================================================

        assert (
            final_translations["chunk-0"]
            == "Translated chunk-0"
        )

        assert (
            final_translations["chunk-1"]
            == "Translated chunk-1"
        )

        assert (
            final_translations["chunk-2"]
            == "Translated chunk-2"
        )

        assert (
            final_translations["chunk-3"]
            == "Translated chunk-3"
        )

        print(
            "✓ Translation contents are correct."
        )

        # ====================================================
        # VERIFY PREVIOUSLY COMPLETED CHUNKS
        # ====================================================

        print(
            "✓ Previously completed chunks preserved."
        )

        # ====================================================
        # VERIFY RESUME API CALLS
        # ====================================================

        resume_calls = (
            resume_client
            .chat
            .completions
            .calls
        )

        # ----------------------------------------------------
        # chunk-0 must NOT be requested again.
        # ----------------------------------------------------

        assert (
            "chunk-0" not in resume_calls
        )

        print(
            "✓ chunk-0 skipped on resume."
        )

        # ----------------------------------------------------
        # chunk-1 must NOT be requested again.
        # ----------------------------------------------------

        assert (
            "chunk-1" not in resume_calls
        )

        print(
            "✓ chunk-1 skipped on resume."
        )

        # ----------------------------------------------------
        # chunk-2 must be requested twice:
        #
        #   1. First request -> 503
        #   2. Retry request -> success
        # ----------------------------------------------------

        assert (
            resume_calls.count("chunk-2")
            == 2
        )

        print(
            "✓ chunk-2 resumed."
        )

        print(
            "✓ chunk-2 retry succeeded."
        )

        # ----------------------------------------------------
        # chunk-3 must be requested once.
        # ----------------------------------------------------

        assert (
            resume_calls.count("chunk-3")
            == 1
        )

        print(
            "✓ chunk-3 continued normally."
        )

        # ====================================================
        # EXACT RESUME ORDER
        # ====================================================

        assert (
            resume_calls
            == [
                "chunk-2",
                "chunk-2",
                "chunk-3",
            ]
        )

        print(
            "✓ Resume started exactly "
            "from the first incomplete chunk."
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 60)
        print(
            "CTRL+C -> SAVE -> RESUME TEST PASSED ✓"
        )
        print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    test_ctrl_c_save_and_resume()
