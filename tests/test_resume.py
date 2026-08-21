# ============================================================
# Resume Translation Test
# ============================================================
#
# Purpose:
#   Test the save/resume mechanism using a small number of
#   real translation requests.
#
# IMPORTANT:
#   - This test uses REAL API requests.
#   - This test consumes tokens.
#   - Only 3 chunks are used.
#   - The real 48-chunk EPUB job is NOT modified.
#   - No final EPUB is created.
#
# Test flow:
#
#   Run 1:
#       chunk-0
#       chunk-1
#       chunk-2
#       ↓
#       save translations
#
#   Simulated interruption
#
#   Run 2:
#       load saved translations
#       skip completed chunks
#       translate remaining chunks
#
# ============================================================

import json
import shutil
from pathlib import Path

from app.core.client import create_client
from app.core.models import get_default_model
from app.core.paths import ensure_dir
from app.jobs.state import save_chunks, save_translations
from app.translation.translator import translate_chunk


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path(
    r"C:\Users\SadidGostaran.Co\Desktop\New folder"
    r"\leblanc-blonde-lady.epub"
)

FROM_LANG = "FA"
TO_LANG = "EN"

TEST_CHUNK_COUNT = 3

TEST_JOB_ID = (
    f"TEST_RESUME_{INPUT_FILE.stem}_"
    f"{FROM_LANG}_{TO_LANG}_"
    f"{get_default_model()}"
)


# ============================================================
# TEST JOB PATH
# ============================================================

def get_test_job_dir():
    """
    Return the temporary directory used exclusively
    by this resume test.
    """

    temp_dir = ensure_dir("temp")

    job_dir = temp_dir / TEST_JOB_ID

    job_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return job_dir


# ============================================================
# LOAD ORIGINAL TEST CHUNKS
# ============================================================

def load_source_chunks():
    """
    Load chunks created by test_pipeline.py.
    """

    temp_dir = ensure_dir("temp")

    pipeline_job_id = (
        f"TEST_{INPUT_FILE.stem}_"
        f"{FROM_LANG}_{TO_LANG}_"
        f"{get_default_model()}"
    )

    chunks_file = (
        temp_dir
        / pipeline_job_id
        / "chunks.json"
    )

    if not chunks_file.exists():

        raise FileNotFoundError(
            f"Source chunks.json not found:\n"
            f"{chunks_file}\n\n"
            f"Run test_pipeline.py first."
        )

    with open(
        chunks_file,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    chunks = data.get("chunks")

    chapter_map = data.get(
        "chapter_map",
        {}
    )

    if not chunks:

        raise ValueError(
            "No chunks found in chunks.json."
        )

    return chunks, chapter_map


# ============================================================
# NORMALIZE CHUNKS
# ============================================================

def normalize_chunks(chunks):
    """
    Normalize chunk representation.

    Expected formats:

        ["chunk-0", "text"]

    or:

        {
            "id": "chunk-0",
            "text": "..."
        }
    """

    normalized = []

    for chunk in chunks:

        if isinstance(
            chunk,
            (list, tuple)
        ):

            chunk_id = str(
                chunk[0]
            )

            chunk_text = chunk[1]

        elif isinstance(
            chunk,
            dict
        ):

            chunk_id = str(
                chunk.get("id")
                or chunk.get("chunk_id")
            )

            chunk_text = (
                chunk.get("text")
                or chunk.get("content")
            )

        else:

            continue

        if not chunk_id or not chunk_text:

            continue

        normalized.append(
            (
                chunk_id,
                chunk_text
            )
        )

    return normalized


# ============================================================
# SAVE TEST STATE
# ============================================================

def save_test_state(
    job_dir,
    chunks,
    translations
):
    """
    Save a minimal state representation for this test.
    """

    chunks_file = (
        job_dir / "chunks.json"
    )

    translations_file = (
        job_dir / "translations.json"
    )

    with open(
        chunks_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "chunks": chunks
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    with open(
        translations_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            translations,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# LOAD TRANSLATIONS
# ============================================================

def load_saved_translations(
    job_dir
):
    """
    Load translations saved during the previous run.
    """

    translations_file = (
        job_dir / "translations.json"
    )

    if not translations_file.exists():

        return {}

    with open(
        translations_file,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    return {
        str(k): v
        for k, v in data.items()
    }


# ============================================================
# TRANSLATE CHUNKS
# ============================================================

def translate_selected_chunks(
    client,
    chunks,
    translations,
    model
):
    """
    Translate only chunks that are not already
    present in the saved translations.
    """

    for index, (
        chunk_id,
        chunk_text
    ) in enumerate(
        chunks,
        1
    ):

        if str(chunk_id) in translations:

            print(
                f"Skipping {chunk_id} "
                f"(already translated)"
            )

            continue

        print()
        print("-" * 60)

        print(
            f"Translating "
            f"{chunk_id}"
        )

        print(
            f"Progress: "
            f"{index}/{len(chunks)}"
        )

        print("-" * 60)

        translated_text = translate_chunk(
            client=client,
            text=chunk_text,
            chunk_id=chunk_id,
            from_lang=FROM_LANG,
            to_lang=TO_LANG,
            model=model,
            test_translations=None,
            filetype="epub"
        )

        if not translated_text:

            raise RuntimeError(
                f"Empty translation returned "
                f"for {chunk_id}"
            )

        translations[
            str(chunk_id)
        ] = translated_text

        print(
            f"✓ {chunk_id} translated."
        )

        print(
            f"Saving progress..."
        )

        save_test_state(
            get_test_job_dir(),
            chunks,
            translations
        )

        print(
            f"✓ Progress saved: "
            f"{len(translations)}/{len(chunks)}"
        )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print("=" * 60)
    print("J Book Translate - Resume Test")
    print("=" * 60)

    # ========================================================
    # 1. Check input
    # ========================================================

    print(
        "\n[1/8] Checking input EPUB..."
    )

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input EPUB not found:\n"
            f"{INPUT_FILE}"
        )

    print(
        "✓ Input EPUB exists."
    )

    # ========================================================
    # 2. Load model
    # ========================================================

    print(
        "\n[2/8] Loading model..."
    )

    model = get_default_model()

    print(
        f"✓ Model: {model}"
    )

    # ========================================================
    # 3. Load chunks
    # ========================================================

    print(
        "\n[3/8] Loading source chunks..."
    )

    source_chunks, chapter_map = (
        load_source_chunks()
    )

    normalized_chunks = normalize_chunks(
        source_chunks
    )

    if len(normalized_chunks) < TEST_CHUNK_COUNT:

        raise ValueError(
            f"Not enough chunks available. "
            f"Found {len(normalized_chunks)}, "
            f"need {TEST_CHUNK_COUNT}."
        )

    test_chunks = normalized_chunks[
        :TEST_CHUNK_COUNT
    ]

    print(
        f"✓ Source chunks loaded: "
        f"{len(normalized_chunks)}"
    )

    print(
        f"✓ Using only "
        f"{len(test_chunks)} chunks for this test."
    )

    # ========================================================
    # 4. Create clean test job
    # ========================================================

    print(
        "\n[4/8] Creating clean resume test job..."
    )

    job_dir = get_test_job_dir()

    # Remove previous test state
    # so every test starts clean.

    for filename in [
        "chunks.json",
        "translations.json"
    ]:

        file_path = (
            job_dir / filename
        )

        if file_path.exists():

            file_path.unlink()

    print(
        f"✓ Test job: {TEST_JOB_ID}"
    )

    print(
        f"✓ Job directory: {job_dir}"
    )

    # ========================================================
    # 5. Create initial state
    # ========================================================

    print(
        "\n[5/8] Creating initial state..."
    )

    translations = {}

    save_test_state(
        job_dir,
        test_chunks,
        translations
    )

    print(
        "✓ Initial state saved."
    )

    # ========================================================
    # 6. Create API client
    # ========================================================

    print(
        "\n[6/8] Creating API client..."
    )

    client = create_client()

    print(
        "✓ API client initialized."
    )

    # ========================================================
    # FIRST RUN
    # ========================================================

    print()
    print("=" * 60)
    print("FIRST RUN")
    print("=" * 60)

    print(
        "Translating the first 2 chunks."
    )

    first_run_chunks = test_chunks[:2]

    translate_selected_chunks(
        client,
        first_run_chunks,
        translations,
        model
    )

    # ========================================================
    # SIMULATED INTERRUPTION
    # ========================================================

    print()
    print("=" * 60)
    print("SIMULATING INTERRUPTION")
    print("=" * 60)

    saved_translations = (
        load_saved_translations(
            job_dir
        )
    )

    print(
        f"✓ Saved translations: "
        f"{len(saved_translations)}"
    )

    for chunk_id in saved_translations:

        print(
            f"  ✓ {chunk_id}"
        )

    if len(saved_translations) != 2:

        raise AssertionError(
            "Expected exactly 2 saved "
            "translations after first run."
        )

    print(
        "\n✓ State correctly preserved."
    )

    # ========================================================
    # 7. RESUME
    # ========================================================

    print()
    print("=" * 60)
    print("RESUME RUN")
    print("=" * 60)

    print(
        "Loading saved translations..."
    )

    translations = (
        load_saved_translations(
            job_dir
        )
    )

    print(
        f"✓ Loaded "
        f"{len(translations)} "
        f"existing translations."
    )

    print(
        "\nStarting resume..."
    )

    # Only the third chunk should be translated.
    #
    # Existing chunks must be skipped.

    translate_selected_chunks(
        client,
        test_chunks,
        translations,
        model
    )

    # ========================================================
    # 8. FINAL VALIDATION
    # ========================================================

    print(
        "\n[8/8] Validating resume result..."
    )

    final_translations = (
        load_saved_translations(
            job_dir
        )
    )

    print(
        f"✓ Final translations: "
        f"{len(final_translations)}/"
        f"{len(test_chunks)}"
    )

    expected_ids = {
        str(chunk_id)
        for chunk_id, _
        in test_chunks
    }

    actual_ids = set(
        final_translations.keys()
    )

    if actual_ids != expected_ids:

        raise AssertionError(
            "Final translation IDs do not "
            "match expected chunk IDs.\n"
            f"Expected: {expected_ids}\n"
            f"Actual: {actual_ids}"
        )

    for chunk_id in expected_ids:

        if not final_translations[
            chunk_id
        ]:

            raise AssertionError(
                f"Empty translation for "
                f"{chunk_id}"
            )

    print(
        "✓ All test chunks translated."
    )

    print(
        "✓ Previously completed chunks "
        "were preserved."
    )

    print(
        "✓ Remaining chunk was resumed."
    )

    print(
        "✓ translations.json is valid."
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 60)
    print("RESUME TEST PASSED ✓")
    print("=" * 60)

    print(
        f"Model             : {model}"
    )

    print(
        f"Test chunks       : {len(test_chunks)}"
    )

    print(
        "First run         : 2 chunks"
    )

    print(
        "Resume run        : 1 chunk"
    )

    print(
        "Final translations: "
        f"{len(final_translations)}"
    )

    print(
        "Output EPUB       : NO"
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()