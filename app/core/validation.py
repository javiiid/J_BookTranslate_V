"""Input and resource validation shared by CLI and web execution."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

MIN_FREE_BYTES = 100 * 1024 * 1024
MAX_BOOK_BYTES = 1024 * 1024 * 1024


def validate_book(path: str | Path, max_bytes: int = MAX_BOOK_BYTES) -> Path:
    book = Path(path)
    if not book.exists() or not book.is_file():
        raise FileNotFoundError(f"Book file does not exist: {book}")
    if book.stat().st_size > max_bytes:
        raise ValueError(f"Book exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")
    suffix = book.suffix.lower()
    if suffix == ".epub":
        try:
            with zipfile.ZipFile(book) as archive:
                if archive.testzip() is not None:
                    raise ValueError("EPUB contains a corrupted ZIP entry.")
                if "mimetype" not in archive.namelist() or archive.read("mimetype").strip() != b"application/epub+zip":
                    raise ValueError("EPUB mimetype is missing or invalid.")
        except zipfile.BadZipFile as exc:
            raise ValueError("EPUB is not a valid ZIP archive.") from exc
    elif suffix == ".pdf":
        try:
            import fitz
            with fitz.open(book) as document:
                if document.page_count < 1:
                    raise ValueError("PDF does not contain any pages.")
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"PDF could not be opened: {exc}") from exc
    else:
        raise ValueError("Only EPUB and PDF files are supported.")
    return book


def ensure_disk_space(path: str | Path, required_bytes: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    required = required_bytes if required_bytes is not None else MIN_FREE_BYTES
    free = shutil.disk_usage(target.parent).free
    if free < required + MIN_FREE_BYTES:
        raise OSError(f"Not enough free disk space. Required at least {required + MIN_FREE_BYTES} bytes.")
