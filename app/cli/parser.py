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

    # ========================================================
    # PROCESSING MODE
    # ========================================================

    parser.add_argument(
        "--mode",
        choices=[
            "batch",
            "resume",
            "test",
            "batchcheck",
            "resumebatch",
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

    return parser.parse_args()