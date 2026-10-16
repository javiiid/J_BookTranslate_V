import argparse
from app.core.models import DEFAULT_MODEL

def parse_args():
    """
    Parse command-line arguments for the Book Translate application.

    Returns:
        argparse.Namespace:
            Parsed command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Translate EPUB and PDF books."
    )

    # ========================================================
    # INPUT / OUTPUT
    # ========================================================

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input EPUB or PDF file."
    )

    parser.add_argument(
        "--output",
        help=(
            "Output file path or output directory. "
            "If omitted, the application determines the output path."
        )
    )

    # ========================================================
    # LANGUAGES
    # ========================================================

    parser.add_argument(
        "--from-lang",
        default="EN",
        help=(
            "Source language code. "
            "Examples: EN, FA, DE, FR"
        )
    )

    parser.add_argument(
        "--to-lang",
        default="FA",
        help=(
            "Target language code. "
            "Examples: EN, FA, DE, FR"
        )
    )

    # ========================================================
    # MODEL
    # ========================================================
    parser.add_argument(
    "--model",
    default=DEFAULT_MODEL,
    help="Model used for translation."
    )

    parser.add_argument(
    "--fallback-model",
    default=None,
    help=(
        "Cheaper model used only after the primary model exhausts "
        "all retries on a chunk. Must be a supported model cheaper "
        "than --model (e.g. gemini-3.1-flash-lite). Omit for no fallback."
    )
    )

    # ========================================================
    # PROCESSING MODE
    # ========================================================

    parser.add_argument(
        "--mode",
        choices=[
            "resume",
            "test",
            "pdfbilingual"
        ],
        default=None,
        help=(
            "Translation processing mode. "
            "If omitted, the default fast translation mode is used."
        )
    )

    # ========================================================
    # DEBUG
    # ========================================================

    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Keep temporary job files after processing "
            "for debugging and recovery."
        )
    )

    parser.add_argument(
        "--prompt",
        help="Custom translation prompt"
        )

    # ========================================================
    # STYLE PRESET
    # ========================================================

    parser.add_argument(
        "--style",
        choices=["literary", "technical", "conversational", "formal"],
        default="literary",
        help="Translation style preset (default: literary)"
        )

    parser.add_argument(
        "--outputs",
        default=None,
        help=(
            "Additional output formats to generate after translation, "
            "comma-separated (e.g. json_segments,txt_bilingual,docx) "
            "or 'all'. Supported: json_segments, txt_bilingual, "
            "markdown, docx, translated_pdf, bilingual_pdf, "
            "srt (book sources: estimated timing), quality_report. "
            "Note: translated_epub is the job's primary output for EPUB "
            "sources and is never an extra format."
        )
    )

    return parser.parse_args()