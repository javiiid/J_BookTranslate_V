# ============================================================
# Pipeline Offline Test
# ============================================================

from pathlib import Path
import json

from app.pipeline.epub_handler import EPUBHandler
from app.jobs.state import (
    ensure_temp_structure,
    save_chunks,
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

INPUT_FILE = (
    r"C:\Users\SadidGostaran.Co\Desktop\New folder"
    r"\leblanc-blonde-lady.epub"
)

FROM_LANG = "FA"
TO_LANG = "EN"
MODEL = "gpt-5.6-terra"


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print("=" * 60)
    print("KALIMA - Pipeline Offline Test")
    print("=" * 60)

    # ========================================================
    # 1. Check input
    # ========================================================

    print("\n[1/6] Checking input EPUB...")

    input_path = Path(INPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input EPUB not found:\n{input_path}"
        )

    if input_path.suffix.lower() != ".epub":
        raise ValueError(
            "Input file must be an EPUB file."
        )

    print("✓ Input EPUB exists.")
    print(f"  File: {input_path}")

    # ========================================================
    # 2. Create test job
    # ========================================================

    print("\n[2/6] Creating test job...")

    job_id = (
        f"TEST_{input_path.stem}_"
        f"{FROM_LANG}_{TO_LANG}_"
        f"{MODEL}"
    )

    paths = ensure_temp_structure(job_id)

    print("✓ Test job created.")
    print(f"  Job ID: {job_id}")
    print(f"  Job directory: {paths['job_dir']}")

    # ========================================================
    # 3. Check temporary structure
    # ========================================================

    print("\n[3/6] Checking temporary structure...")

    required_paths = [
        "job_dir",
        "state_file",
        "chunks_file",
        "translations_file",
        "progress_log",
    ]

    for name in required_paths:

        if name not in paths:
            raise AssertionError(
                f"Missing path: {name}"
            )

        print(
            f"✓ {name}: {paths[name]}"
        )

    # ========================================================
    # 4. Build chunks
    # ========================================================

    print("\n[4/6] Building EPUB chunks...")
    print("IMPORTANT: No API request will be sent.")

    all_chunks, chapter_map = (
        EPUBHandler.build_chunks(
            input_path
        )
    )

    if not all_chunks:
        raise AssertionError(
            "No chunks were created."
        )

    print(
        f"\n✓ Total chunks created: "
        f"{len(all_chunks)}"
    )

    print(
        f"✓ Chapter map entries: "
        f"{len(chapter_map)}"
    )

    # ========================================================
    # 5. Save and verify chunks.json
    # ========================================================

    print("\n[5/6] Saving chunks...")

    save_chunks(
        paths,
        all_chunks,
        chapter_map
    )

    chunks_file = paths["chunks_file"]

    if not chunks_file.exists():
        raise AssertionError(
            "chunks.json was not created."
        )

    print(
        f"✓ chunks.json created:"
        f"\n  {chunks_file}"
    )

    # --------------------------------------------------------
    # Read chunks.json
    # --------------------------------------------------------

    with open(
        chunks_file,
        "r",
        encoding="utf-8"
    ) as f:

        saved_data = json.load(f)

    print(
        f"✓ chunks.json loaded successfully."
    )

    # --------------------------------------------------------
    # Validate structure
    # --------------------------------------------------------

    if not isinstance(saved_data, dict):
        raise AssertionError(
            "chunks.json must contain a JSON object."
        )

    print(
        f"✓ chunks.json contains "
        f"{len(saved_data)} top-level entries."
    )

    # ========================================================
    # 6. Final verification
    # ========================================================

    print()
    print("=" * 60)
    print("PIPELINE OFFLINE TEST")
    print("=" * 60)

    print(
        "✓ Input EPUB             : OK"
    )

    print(
        "✓ Job structure           : OK"
    )

    print(
        "✓ EPUB parsing            : OK"
    )

    print(
        "✓ Chunk building          : OK"
    )

    print(
        f"✓ Chunks created          : {len(all_chunks)}"
    )

    print(
        "✓ chunks.json             : OK"
    )

    print(
        "✓ Chapter map             : OK"
    )

    print(
        "✓ API request             : NOT SENT"
    )

    print(
        "✓ Token usage             : 0"
    )

    print()
    print(
        "PIPELINE OFFLINE TEST PASSED ✓"
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()