import json
import zipfile

from app.reader.service import chapter_blocks
from app.reader.page import reader_page


def test_chapter_blocks_pairs_original_and_translation(tmp_path):
    chunks = {
        "chunks": [
            ["chunk-0", "The machine stopped suddenly."],
            ["chunk-1", "The operator restarted it."],
            ["chunk-2", "Another chapter."],
        ],
        "chapter_map": {
            "chunk-0": {"item": "chapter1.xhtml", "pos": 0},
            "chunk-1": {"item": "chapter1.xhtml", "pos": 1},
            "chunk-2": {"item": "chapter2.xhtml", "pos": 0},
        },
    }
    translations = {
        "chunk-0": "دستگاه ناگهان متوقف شد.",
        "chunk-1": "اپراتور آن را دوباره راه‌اندازی کرد.",
        "chunk-2": "فصل دیگری.",
    }
    chunks_file = tmp_path / "chunks.json"
    translations_file = tmp_path / "translations.json"
    chunks_file.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    translations_file.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")

    epub = tmp_path / "book.epub"
    container = '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>'
    opf = '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'
    chapter = "<html><head><title>Chapter</title></head><body><h1>Chapter</h1><p>Translated</p></body></html>"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/chapter1.xhtml", chapter)
        archive.writestr("OEBPS/chapter2.xhtml", chapter)

    paths = {"chunks_file": chunks_file, "translations_file": translations_file}
    blocks = chapter_blocks(paths, epub, 0)

    assert [item["id"] for item in blocks] == ["chunk-0", "chunk-1"]
    assert blocks[0]["original"] == "The machine stopped suddenly."
    assert blocks[0]["translation"] == "دستگاه ناگهان متوقف شد."
    assert blocks[1]["translation"] == "اپراتور آن را دوباره راه‌اندازی کرد."


def test_chapter_blocks_sanitizes_parallel_html(tmp_path):
    chunks_file = tmp_path / "chunks.json"
    translations_file = tmp_path / "translations.json"
    chunks_file.write_text(json.dumps({
        "chunks": [["chunk-0", '<p>Original</p><script>alert(1)</script>']],
        "chapter_map": {"chunk-0": {"item": "chapter.xhtml", "pos": 0}},
    }), encoding="utf-8")
    translations_file.write_text(json.dumps({
        "chunk-0": '<p>ترجمه</p><a href="javascript:alert(1)">bad</a>',
    }, ensure_ascii=False), encoding="utf-8")

    epub = tmp_path / "book.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfile full-path="content.opf"/></container>')
        archive.writestr("content.opf", '<package><manifest><item id="c1" href="chapter.xhtml"/></manifest><spine><itemref idref="c1"/></spine></package>')
        archive.writestr("chapter.xhtml", "<html><body><p>Translated</p></body></html>")

    blocks = chapter_blocks({"chunks_file": chunks_file, "translations_file": translations_file}, epub, 0)
    assert "script" not in blocks[0]["original_html"]
    assert "javascript:" not in blocks[0]["translation_html"]


def test_reader_page_exposes_translation_modes():
    page = reader_page("job-1")
    assert 'id="mode"' in page
    assert 'value="bilingual"' in page
    assert "'/blocks'" in page
