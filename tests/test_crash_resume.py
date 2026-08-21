
# ============================================================
# Crash / Exception -> Save Progress -> Resume Test
# ============================================================

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.translation.translator import process_translations


# ============================================================
# FAKE API CLIENT
# ============================================================

class FakeCompletions:
    """
    Fake OpenAI-compatible API client.

    Behaviour:

        chunk-0 -> success
        chunk-1 -> success
        chunk-2 -> unexpected exception
        chunk-3 -> success

    During resume:

        chunk-2 -> success
        chunk-3 -> success
    """

    def __init__(self):
        self.calls = []
        self.chunk_attempts = {}

        # Used only during the first phase.
        self.crash_enabled = True

    def create(
        self,
        model,
        messages,
        temperature=0.2,
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
        # Simulate an unexpected application/API exception.
        #
        # This is NOT a retryable HTTP error.
        # ----------------------------------------------------

        if (
            chunk_id == "chunk-2"
            and self.crash_enabled
        ):
            print(
                "Simulating unexpected application exception..."
            )

            raise RuntimeError(
                "Simulated unexpected failure "
                "during chunk-2."
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

    return {
        "translations_file": (
            temp_dir / "translations.json"
        ),
    }


# ============================================================
# LOAD TRANSLATIONS
# ============================================================

def load_translations(
    translations_file,
):
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

def test_crash_save_and_resume():

    print()
    print("=" * 60)
    print(
        "CRASH / EXCEPTION -> SAVE PROGRESS -> RESUME TEST"
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
            "PHASE 1: RUN UNTIL UNEXPECTED EXCEPTION"
        )
        print("=" * 60)

        client = FakeClient()

        # ====================================================
        # RUN
        # ====================================================

        try:

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

        except RuntimeError as error:

            print()
            print(
                "✓ RuntimeError received."
            )

            print(
                f"✓ Error: {error}"
            )

        else:

            raise AssertionError(
                "Expected RuntimeError "
                "was not raised."
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
        # chunk-0 must exist.
        # ----------------------------------------------------

        assert (
            "chunk-0" in saved
        )

        print(
            "✓ chunk-0 preserved."
        )

        # ----------------------------------------------------
        # chunk-1 must exist.
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
            "✓ chunk-3 was never processed."
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
            phase1_calls
            == [
                "chunk-0",
                "chunk-1",
                "chunk-2",
            ]
        )

        print(
            "✓ Processing stopped exactly at "
            "the failed chunk."
        )

        # ====================================================
        # PHASE 2
        # ====================================================

        print()
        print("=" * 60)
        print(
            "PHASE 2: RESUME AFTER EXCEPTION"
        )
        print("=" * 60)

        # ----------------------------------------------------
        # Simulate a new application process.
        # ----------------------------------------------------

        resume_client = FakeClient()

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # The application has recovered, so the simulated
        # crash is disabled.
        # ----------------------------------------------------

        resume_client.chat.completions.crash_enabled = (
            False
        )

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
        # RESUME
        # ====================================================

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
        # FINAL STATE
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
        # All chunks must exist.
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
        # VERIFY CONTENT
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
        # VERIFY RESUME SKIPPING
        # ====================================================

        resume_calls = (
            resume_client
            .chat
            .completions
            .calls
        )

        # ----------------------------------------------------
        # Previously completed chunks must be skipped.
        # ----------------------------------------------------

        assert (
            "chunk-0" not in resume_calls
        )

        print(
            "✓ chunk-0 skipped on resume."
        )

        assert (
            "chunk-1" not in resume_calls
        )

        print(
            "✓ chunk-1 skipped on resume."
        )

        # ----------------------------------------------------
        # Failed chunk must be retried.
        # ----------------------------------------------------

        assert (
            resume_calls.count("chunk-2")
            == 1
        )

        print(
            "✓ chunk-2 resumed successfully."
        )

        # ----------------------------------------------------
        # Following chunk must continue normally.
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
                "chunk-3",
            ]
        )

        print(
            "✓ Resume started exactly from "
            "the first incomplete chunk."
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 60)
        print(
            "CRASH -> SAVE -> RESUME TEST PASSED ✓"
        )
        print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    test_crash_save_and_resume()
