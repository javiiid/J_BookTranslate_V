# Seed a demo COMPLETED job so the new PDF outputs can be checked in the UI.
#
# No API key, no spending: translations are local sample text, only the
# output writers run (the same code the real pipeline calls).
#
# Run:   python scripts/seed_demo_job.py
# Then:  restart the backend (python -m app.web) so it picks the job up,
#        and open the URLs printed at the end:
#          React monitor : http://localhost:5173/jobs/<id>  (Overview + Files tabs)
#          Python monitor: http://127.0.0.1:8765/workspace/job/<id>
#
# Cleanup: delete data/jobs/<id>.json, data/uploads/demo-book.epub and
# output/web/<id>_*, then restart the backend.

from __future__ import annotations

import json
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.paths import ensure_dir  # noqa: E402
from app.output.formats import TRANSLATION_OUTPUTS, generate_outputs  # noqa: E402
from app.output.segments import build_segments  # noqa: E402

BOOK_TITLE = "Demo Book"
PARAGRAPHS_PER_CHAPTER = 120
CHAPTERS = 4

FILLER = (
    "with some filler words for the demo book to make each chapter long "
    "enough that the semantic chunker splits it into several chunks"
)

TARGETS = [
    "متن پژوهش شماره {i} پایان.",
    "این یک جمله نمونه برای بررسی صفحه‌بندی است.",
    "خوانایی و چیدمان خروجی در این بخش دیده می‌شود.",
]


def make_epub(path: Path) -> None:
    chapters = []
    for c in range(CHAPTERS):
        paras = "".join(
            f"<p>Original sentence number {c * PARAGRAPHS_PER_CHAPTER + p} "
            f"{FILLER}.</p>"
            for p in range(PARAGRAPHS_PER_CHAPTER)
        )
        chapters.append(
            f"<html xmlns='http://www.w3.org/1999/xhtml'>"
            f"<head><title>Chapter {c + 1}</title></head>"
            f"<body><h1>Chapter {c + 1}</h1>{paras}</body></html>"
        )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
            '<rootfiles><rootfile full-path="OPS/book.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        items = "".join(
            f'<item id="ch{c}" href="ch{c}.xhtml" media-type="application/xhtml+xml"/>'
            for c in range(CHAPTERS)
        )
        refs = "".join(f'<itemref idref="ch{c}"/>' for c in range(CHAPTERS))
        archive.writestr(
            "OPS/book.opf",
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:identifier id="id">demo-book</dc:identifier><dc:title>{BOOK_TITLE}</dc:title>'
            '<dc:language>en</dc:language></metadata>'
            f"<manifest>{items}</manifest><spine>{refs}</spine></package>",
        )
        for c, content in enumerate(chapters):
            archive.writestr(f"OPS/ch{c}.xhtml", content)


def main() -> None:
    from app.pipeline.epub_handler import EPUBHandler

    job_id = f"demo-manual-{uuid.uuid4().hex[:6]}"
    upload_dir = ensure_dir("data") / "uploads"
    web_out = ensure_dir("output") / "web"
    meta_dir = ensure_dir("data") / "jobs"

    source = upload_dir / "demo-book.epub"
    make_epub(source)

    all_chunks, chapter_map, _contexts = EPUBHandler.build_chunks(source)
    flagged_pos = min(5, len(all_chunks) - 1)
    translations = {}
    for pos, (chunk_id, _source) in enumerate(all_chunks):
        text = TARGETS[pos % len(TARGETS)].format(i=pos)
        if pos == flagged_pos:
            text += " {NOTE: نمونه پرچم برای هایلایت}"
        translations[str(chunk_id)] = text

    segments = build_segments(all_chunks, translations, chapter_map, "epub")
    # quality_report has no scorer here, so it lands in `skipped` --
    # exactly like a real job without QA requested.
    result = generate_outputs(
        segments,
        requested=sorted(TRANSLATION_OUTPUTS),
        output_dir=web_out,
        base_name=f"{job_id}_demo-book_fa",
        filetype="epub",
        title=BOOK_TITLE,
        to_lang="FA",
    )

    # Primary output: the demo reuses the source EPUB so the main
    # download link works; the reviewed files are the extras below.
    primary = web_out / f"{job_id}_demo-book_fa_demo.epub"
    shutil.copyfile(source, primary)

    payload = {
        "id": job_id,
        "filename": "demo-book.epub",
        "input_path": str(source),
        "filetype": "epub",
        "file_size": source.stat().st_size,
        "options": {
            "from_lang": "EN", "to_lang": "FA", "model": "demo (no API)",
            "mode": "test", "prompt": "", "debug": "false",
        },
        "source_language": "EN",
        "target_language": "FA",
        "model": "demo (no API)",
        "mode": "test",
        "status": "completed",
        "created_at": "2026-10-15T00:00:00+00:00",
        "started_at": "2026-10-15T00:00:00+00:00",
        "updated_at": "2026-10-15T00:00:00+00:00",
        "pipeline_job_id": None,
        "paths": None,
        "output_path": str(primary),
        "error": None,
        "progress": {"completed": len(all_chunks), "total": len(all_chunks)},
        "assets": {name: str(path) for name, path in result["generated"].items()},
        "qa_report": result.get("qa_report"),
        "quality": result.get("quality"),
        "style": "literary",
    }
    (meta_dir / f"{job_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"seeded job {job_id}: {len(all_chunks)} chunks, "
          f"{len(result['generated'])} outputs, "
          f"{len(result['skipped'])} skipped {sorted(result['skipped'])}")
    print("1. restart the backend:  python -m app.web")
    print(f"2. React monitor:        http://localhost:5173/jobs/{job_id}")
    print(f"3. Python monitor:       http://127.0.0.1:8765/workspace/job/{job_id}")
    print("   Files tab -> download translated_pdf / bilingual_pdf and look:")
    print("   few pages (not one per segment), title on page 1,")
    print("   bilingual: original then translation per pair,")
    print("   Persian shaped right-aligned, one highlighted segment.")
    print(f"   (flagged chunk index: {flagged_pos})")


if __name__ == "__main__":
    main()
