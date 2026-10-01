
# ============================================================
# Translator Single-Chunk Test
# ============================================================
#
# Purpose:
#   Test the complete translation layer with exactly ONE chunk.
#
# IMPORTANT:
#   - This test sends ONE real API request.
#   - It consumes tokens.
#   - It does NOT translate the entire EPUB.
#   - It does NOT create an output EPUB.
#   - It does NOT modify the real translation job.
#
# ============================================================

import json
from pathlib import Path

from app.core.client import create_client
from app.core.models import get_default_model
from app.core.paths import ensure_dir
from app.translation.translator import _clean_translation, translate_chunk


# ============================================================
# TEST CONFIGURATION
# ============================================================

INPUT_FILE = (
    Path(
        r"C:\Users\SadidGostaran.Co\Desktop\New folder"
        r"\leblanc-blonde-lady.epub"
    )
)

FROM_LANG = "FA"
TO_LANG = "EN"


# ============================================================
# FIND TEST JOB
# ============================================================

def find_test_chunks_file():
    """
    Find the chunks.json file created by test_pipeline.py.
    """

    temp_dir = ensure_dir("temp")

    test_job_id = (
        f"TEST_{INPUT_FILE.stem}_"
        f"{FROM_LANG}_{TO_LANG}_"
        f"{get_default_model()}"
    )

    job_dir = temp_dir / test_job_id
    chunks_file = job_dir / "chunks.json"

    return chunks_file


# ============================================================
# LOAD CHUNK
# ============================================================

def load_first_chunk(chunks_file):
    """
    Load chunk-0 from chunks.json.
    """

    if not chunks_file.exists():

        raise FileNotFoundError(
            f"chunks.json not found:\n{chunks_file}\n\n"
            "Run test_pipeline.py first."
        )

    with open(
        chunks_file,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    # --------------------------------------------------------
    # Expected structure:
    #
    # {
    #     "chunks": [...],
    #     "chapter_map": {...}
    # }
    # --------------------------------------------------------

    chunks = data.get("chunks")

    if chunks is None:

        raise ValueError(
            "chunks.json does not contain "
            "'chunks'."
        )

    if not chunks:

        raise ValueError(
            "chunks.json contains no chunks."
        )

    # --------------------------------------------------------
    # Find chunk-0
    # --------------------------------------------------------

    for chunk in chunks:

        if isinstance(chunk, (list, tuple)):

            chunk_id = str(chunk[0])
            chunk_text = chunk[1]

        elif isinstance(chunk, dict):

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

        if chunk_id == "chunk-0":

            if not chunk_text:

                raise ValueError(
                    "chunk-0 has empty text."
                )

            return chunk_id, chunk_text

    raise ValueError(
        "chunk-0 was not found in chunks.json."
    )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print("=" * 60)
    print("KALIMA - Single Chunk Translator Test")
    print("=" * 60)

    # ========================================================
    # 1. Check input
    # ========================================================

    print("\n[1/6] Checking input EPUB...")

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input EPUB not found:\n{INPUT_FILE}"
        )

    print("✓ Input EPUB exists.")
    print(f"  File: {INPUT_FILE}")

    # ========================================================
    # 2. Get model
    # ========================================================

    print("\n[2/6] Loading model configuration...")

    model = get_default_model()

    print(
        f"✓ Model: {model}"
    )

    # ========================================================
    # 3. Load chunks
    # ========================================================

    print("\n[3/6] Loading chunks...")

    chunks_file = find_test_chunks_file()

    print(
        f"Chunks file:\n{chunks_file}"
    )

    chunk_id, chunk_text = load_first_chunk(
        chunks_file
    )

    print(
        f"✓ Found {chunk_id}"
    )

    print(
        f"✓ Chunk length: "
        f"{len(chunk_text)} characters"
    )

    # --------------------------------------------------------
    # Show a small preview
    # --------------------------------------------------------

    preview = chunk_text[:500]

    print("\nChunk preview:")
    print("-" * 60)
    print(preview)

    if len(chunk_text) > 500:
        print("...")

    print("-" * 60)

    # ========================================================
    # 4. Create API client
    # ========================================================

    print("\n[4/6] Creating API client...")

    client = create_client()

    print(
        "✓ API client initialized."
    )

    # ========================================================
    # 5. Send ONE API request
    # ========================================================

    print("\n[5/6] Translating chunk-0...")
    print()
    print("WARNING:")
    print("This test sends ONE real API request.")
    print("This request consumes tokens.")
    print()

    try:

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

    except KeyboardInterrupt:

        print(
            "\n✗ Translation interrupted by user."
        )

        raise

    # ========================================================
    # 6. Validate response
    # ========================================================

    print("\n[6/6] Validating translation...")

    if not translated_text:

        raise AssertionError(
            "Translator returned empty text."
        )

    if not isinstance(
        translated_text,
        str
    ):

        raise AssertionError(
            "Translator result is not a string."
        )

    print(
        "✓ Translation received."
    )

    print(
        f"✓ Translation length: "
        f"{len(translated_text)} characters"
    )

    print("\nTranslated text preview:")
    print("-" * 60)
    print(
        translated_text[:1000]
    )

    if len(translated_text) > 1000:
        print("...")

    print("-" * 60)

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 60)
    print("TRANSLATOR TEST PASSED ✓")
    print("=" * 60)

    print(
        f"Model        : {model}"
    )

    print(
        f"Chunk        : {chunk_id}"
    )

    print(
        f"Input chars  : {len(chunk_text)}"
    )

    print(
        f"Output chars : {len(translated_text)}"
    )

    print(
        "API requests : 1"
    )

    print(
        "EPUB created : NO"
    )

    print(
        "Full book    : NO"
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()


class TestLeadingSeparator:
    """The whitespace between two translations, which the save path relies on.

    Chunks are rejoined with ``"".join``, so the separator between one chunk's
    translation and the next has to live inside one of them. It used to be
    stripped away, and a 60-chunk book came out with 26 paragraph boundaries
    welded shut -- which is what "the texts get glued together" turned out to be.
    """

    def test_a_paragraph_translation_comes_back(self) -> None:
        # The first version of the fix put the return inside the code-fence
        # branch, so an ordinary translation -- no fence, the normal case -- fell
        # off the end of the function and returned None. Every chunk then failed
        # as "became empty after cleanup".
        assert _clean_translation("سلام دنیا.", "<p>Hello</p>") == "سلام دنیا."

    def test_surrounding_whitespace_is_still_removed(self) -> None:
        # The point of the cleanup: the model's own padding goes.
        assert _clean_translation("  ترجمه  ", "<p>x</p>").strip() == "ترجمه"

    def test_a_leading_newline_is_restored(self) -> None:
        # The source chunk began with the newline that followed the previous
        # chunk's closing tag, and that newline is the paragraph break.
        out = _clean_translation("متن", "\n\n<p>Something</p>")
        assert out.startswith("\n\n")
        assert out.strip() == "متن"

    def test_a_source_with_no_leading_whitespace_adds_none(self) -> None:
        assert _clean_translation("متن", "<p>Something</p>") == "متن"

    def test_no_source_still_works(self) -> None:
        assert _clean_translation("متن") == "متن"

    def test_the_code_fence_is_still_removed(self) -> None:
        fenced = "```html\n<p>ترجمه</p>\n```"
        assert _clean_translation(fenced, "<p>x</p>").strip() == "<p>ترجمه</p>"

    def test_translations_still_join_back_to_their_neighbours(self) -> None:
        # The end-to-end shape, with the markup each translation is responsible
        # for -- the `<p>` wrapper is part of the chunk, not of the model's output.
        first = _clean_translation("پاراگراف اول.", "<p>First.</p>")
        second = _clean_translation("پاراگراف دوم.", "\n<p>Second.</p>")
        document = f"<p>{first}</p>{second}<p>پاراگراف سوم.</p>"
        # The paragraph break survived: the closing tag is not glued straight to
        # the next sentence. This is the exact shape that was broken.
        assert "</p>پاراگراف دوم." not in document
        assert "</p>\nپاراگراف دوم." in document
