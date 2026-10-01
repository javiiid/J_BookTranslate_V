import json
import zipfile
from pathlib import Path

import pytest

from app.output.convert import _extract_epub, convert_file
from app.pipeline.epub_handler import EPUBHandler


@pytest.mark.parametrize("semantic_chunking", [False, True])
def test_convert_epub_with_current_chunk_contract(tmp_path, monkeypatch, semantic_chunking):
    monkeypatch.setattr(
        "app.pipeline.epub_handler._chunk_settings",
        lambda: {
            "semantic_chunking": semantic_chunking,
            "chunk_max_tokens": 120,
            "chunk_context_window": 2,
        },
    )
    input_path = tmp_path / "book.epub"
    chapter = "<h1>Conversion sample</h1>" + "".join(
        f"<p>Paragraph {index} contains enough source text for a complete conversion test. "
        "This paragraph should survive extraction and output generation.</p>"
        for index in range(8)
    )
    with zipfile.ZipFile(input_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr("OEBPS/content.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">sample</dc:identifier><dc:title>Sample</dc:title><dc:language>en</dc:language></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>')
        archive.writestr("OEBPS/chapter.xhtml", chapter)

    result = convert_file(input_path, tmp_path / "output", ["json_segments", "markdown"])

    assert set(result["generated"]) == {"json_segments", "markdown"}
    payload = json.loads(Path(result["generated"]["json_segments"]).read_text(encoding="utf-8"))
    segments = payload["segments"]
    assert segments
    assert all(segment["source"] == segment["target"] for segment in segments)
    assert all(segment["chapter"] == "OEBPS/chapter.xhtml" for segment in segments)
    combined = " ".join(segment["source"] for segment in segments)
    for index in range(8):
        assert combined.count(f"Paragraph {index}") == 1
    assert Path(result["generated"]["markdown"]).stat().st_size > 0


def test_epub_conversion_does_not_include_translation_context(monkeypatch):
    chunks = [("chunk-0", "<p>Source text</p>")]
    chapter_map = {"chunk-0": ("chapter.xhtml", 0)}
    monkeypatch.setattr(
        EPUBHandler,
        "build_chunks",
        lambda input_path: (chunks, chapter_map, {"chunk-0": "Context for translation only"}),
    )

    assert _extract_epub(Path("sample.epub")) == (chunks, chapter_map)
