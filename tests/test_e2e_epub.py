# ============================================================
# tests/test_e2e_epub.py
#
# End-to-End EPUB Translation Test
#
# WARNING:
# This test sends REAL API requests.
# Only the first 10 chunks are translated.
#
# Flow:
#
# EPUB
#   ↓
# Build chunks
#   ↓
# Select first 10 chunks
#   ↓
# Translate
#   ↓
# Save translations
#   ↓
# Reassemble EPUB
#   ↓
# Validate output
#
# Run:
#
# python -m tests.test_e2e_epub
# ============================================================

import sys
import zipfile
from pathlib import Path

from app.core.config import read_config
from app.core.client import create_client
from app.core.models import get_default_model
from app.core.paths import create_job_id, ensure_temp_structure
from app.jobs.state import save_chunks, save_translations
from app.pipeline.epub_handler import EPUBHandler
from app.pipeline.epub_pipeline import reassemble_translation
from app.translation.translator import process_translations


# ============================================================
# Configuration
# ============================================================

MAX_CHUNKS = 5

INPUT_EPUB = Path(
    r"C:\Users\SadidGostaran.Co\Desktop\New folder\leblanc-blonde-lady.epub"
)

FROM_LANG = "EN"
TO_LANG = "FA"

TEST_JOB_PREFIX = "TEST_E2E"

MODEL = get_default_model()


# ============================================================
# Helpers
# ============================================================

def print_step(number, total, message):
    """Print a formatted test step."""

    print()
    print(f"[{number}/{total}] {message}")


def validate_epub(path):
    """
    Validate that the generated file exists
    and is a readable EPUB/ZIP archive.
    """

    if not path.exists():
        raise AssertionError(
            f"Output EPUB does not exist: {path}"
        )

    if path.stat().st_size == 0:
        raise AssertionError(
            "Output EPUB is empty."
        )

    if not zipfile.is_zipfile(path):
        raise AssertionError(
            "Output file is not a valid ZIP/EPUB archive."
        )

    with zipfile.ZipFile(path, "r") as epub:

        names = epub.namelist()

        if "mimetype" not in names:
            raise AssertionError(
                "EPUB does not contain mimetype."
            )

        if not any(
            name.endswith(".xhtml")
            or name.endswith(".html")
            for name in names
        ):
            raise AssertionError(
                "EPUB contains no XHTML/HTML content."
            )

    return True


# ============================================================
# Main Test
# ============================================================

def main():

    TOTAL_STEPS = 9

    print("=" * 60)
    print("END-TO-END EPUB TRANSLATION TEST")
    print("=" * 60)

    print()
    print("WARNING:")
    print(
        f"This test sends up to {MAX_CHUNKS} "
        "REAL API requests."
    )
    print("API tokens WILL be consumed.")
    print()
    print(f"Input : {INPUT_EPUB}")
    print(f"From  : {FROM_LANG}")
    print(f"To    : {TO_LANG}")
    print(f"Model : {MODEL}")
    print("=" * 60)

    # ========================================================
    # 1. Check input
    # ========================================================

    print_step(
        1,
        TOTAL_STEPS,
        "Checking input EPUB..."
    )

    if not INPUT_EPUB.exists():
        print(
            f"✗ Input EPUB not found:\n"
            f"{INPUT_EPUB}"
        )
        sys.exit(1)

    if INPUT_EPUB.suffix.lower() != ".epub":
        print("✗ Input file is not an EPUB.")
        sys.exit(1)

    print("✓ Input EPUB exists.")
    print(f"File: {INPUT_EPUB}")

    # ========================================================
    # 2. Load configuration/model
    # ========================================================

    print_step(
        2,
        TOTAL_STEPS,
        "Loading configuration and model..."
    )

    config = read_config()

    if not config.get("openai"):
        raise AssertionError(
            "OpenAI configuration not found."
        )

    if not config["openai"].get("api_key"):
        raise AssertionError(
            "OpenAI API key not found."
        )

    print("✓ Configuration loaded.")
    print(f"✓ Model: {MODEL}")

    # ========================================================
    # 3. Build EPUB chunks
    # ========================================================

    print_step(
        3,
        TOTAL_STEPS,
        "Building EPUB chunks..."
    )

    all_chunks, chapter_map = (
        EPUBHandler.build_chunks(
            str(INPUT_EPUB)
        )
    )

    print(
        f"✓ Total chunks created: "
        f"{len(all_chunks)}"
    )

    if len(all_chunks) < MAX_CHUNKS:
        raise AssertionError(
            f"EPUB contains only {len(all_chunks)} "
            f"chunks; {MAX_CHUNKS} required."
        )

    # ========================================================
    # 4. Select first 10 chunks
    # ========================================================

    print_step(
        4,
        TOTAL_STEPS,
        f"Selecting first {MAX_CHUNKS} chunks..."
    )

    selected_chunks = all_chunks[:MAX_CHUNKS]

    selected_ids = [
        chunk_id
        for chunk_id, _ in selected_chunks
    ]

    print(
        f"✓ Selected {len(selected_chunks)} chunks."
    )

    print(
        "Chunk IDs:"
    )

    for chunk_id in selected_ids:
        print(f"  ✓ {chunk_id}")

    # Keep only chapter_map entries belonging
    # to the selected chunks.
    selected_chapter_map = {
        chunk_id: chapter_map[chunk_id]
        for chunk_id in selected_ids
        if chunk_id in chapter_map
    }

    print(
        f"✓ Chapter map entries: "
        f"{len(selected_chapter_map)}"
    )

    # ========================================================
    # 5. Create test job
    # ========================================================

    print_step(
        5,
        TOTAL_STEPS,
        "Creating E2E test job..."
    )

    base_job_id = create_job_id(
        str(INPUT_EPUB),
        FROM_LANG,
        TO_LANG,
        MODEL
    )

    job_id = (
        f"{TEST_JOB_PREFIX}_"
        f"{base_job_id}"
    )

    paths = ensure_temp_structure(job_id)

    print(f"✓ Job ID: {job_id}")
    print(f"✓ Job directory: {paths['job_dir']}")

    # Save the selected chunks so the test job
    # is self-contained.
    save_chunks(
        paths,
        selected_chunks,
        selected_chapter_map
    )

    print("✓ Test chunks saved.")

    # ========================================================
    # 6. Create API client
    # ========================================================

    print_step(
        6,
        TOTAL_STEPS,
        "Creating API client..."
    )

    client = create_client()

    print("✓ API client initialized.")

    # ========================================================
    # 7. Translate 10 chunks
    # ========================================================

    print_step(
        7,
        TOTAL_STEPS,
        f"Translating {MAX_CHUNKS} chunks..."
    )

    print()
    print("IMPORTANT:")
    print(
        f"{MAX_CHUNKS} real API requests may be sent."
    )
    print("Tokens will be consumed.")
    print()

    translations = {}

    translations, input_file_id, batch_status = (
        process_translations(
            client,
            selected_chunks,
            translations,
            "fast",
            FROM_LANG,
            TO_LANG,
            paths,
            model=MODEL,
            debug=True,
            chapter_map=selected_chapter_map,
            filetype="epub"
        )
    )

    print()

    print(
        f"✓ Translation finished."
    )

    print(
        f"✓ Translations received: "
        f"{len(translations)}/{MAX_CHUNKS}"
    )

    if len(translations) != MAX_CHUNKS:
        raise AssertionError(
            f"Expected {MAX_CHUNKS} translations, "
            f"received {len(translations)}."
        )

    # ========================================================
    # 8. Save + Reassemble
    # ========================================================

    print_step(
        8,
        TOTAL_STEPS,
        "Saving translations and rebuilding EPUB..."
    )

    save_translations(
        paths,
        translations
    )

    if not paths["translations_file"].exists():
        raise AssertionError(
            "translations.json was not created."
        )

    print(
        f"✓ translations.json created:"
        f"\n  {paths['translations_file']}"
    )

    # --------------------------------------------------------
    # Output path
    # --------------------------------------------------------

    output_dir = (
        INPUT_EPUB.parent
        / "e2e_test_output"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        output_dir
        / (
            f"{INPUT_EPUB.stem}_"
            f"{TO_LANG.lower()}_"
            f"{MODEL}_"
            f"e2e_test.epub"
        )
    )

    print(
        f"Output path:\n"
        f"{output_path}"
    )

    # --------------------------------------------------------
    # Reassemble
    # --------------------------------------------------------

    reassemble_translation(
        str(INPUT_EPUB),
        str(output_path),
        selected_chapter_map,
        translations
    )

    print("✓ EPUB reassembled.")

    # ========================================================
    # 9. Validate output
    # ========================================================

    print_step(
        9,
        TOTAL_STEPS,
        "Validating generated EPUB..."
    )

    validate_epub(output_path)

    print("✓ Output file exists.")
    print("✓ Output is a valid EPUB/ZIP archive.")
    print("✓ mimetype exists.")
    print("✓ XHTML/HTML content exists.")

    # ========================================================
    # Final result
    # ========================================================

    print()
    print("=" * 60)
    print("END-TO-END EPUB TEST PASSED ✓")
    print("=" * 60)

    print()
    print("Summary:")
    print(
        f"✓ Input EPUB        : {INPUT_EPUB.name}"
    )
    print(
        f"✓ Source chunks     : {len(all_chunks)}"
    )
    print(
        f"✓ Tested chunks     : {MAX_CHUNKS}"
    )
    print(
        f"✓ Translations      : {len(translations)}"
    )
    print(
        f"✓ translations.json : OK"
    )
    print(
        f"✓ EPUB reassembly   : OK"
    )
    print(
        f"✓ Output EPUB       : OK"
    )
    print()
    print(
        f"Output:\n{output_path}"
    )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()