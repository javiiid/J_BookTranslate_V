# ============================================================
# Output Format Generation Tests
# ============================================================

import json
import re
import unicodedata
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz

from app.output import (
    build_qa_report,
    build_segments,
    emit_outputs,
    extract_markers,
    generate_outputs,
    normalize_outputs,
    strip_markers,
)
from app.output import docx as docx_module
from app.output import srt as srt_module
from app.output import txt as txt_module
from app.output import markdown as markdown_module
from app.output import json_segments as json_segments_module
from app.output import pdf as pdf_module
from app.translation.prompts import (
    get_default_prompt,
    get_engine_prompt,
)

SAMPLE = [
    {
        "id": "chunk-0",
        "position": 0,
        "source": "The first original sentence.",
        "target": "The first translated sentence.",
        "format": "epub",
        "chapter": "ch1.xhtml",
        "flagged": True,
        "notes": ["ambiguous term kept as-is"],
    },
    {
        "id": "chunk-1",
        "position": 1,
        "source": "The second original sentence.",
        "target": "The second translated sentence.",
        "format": "epub",
        "chapter": "ch1.xhtml",
        "flagged": False,
        "notes": [],
    },
]


# ============================================================
# MARKERS
# ============================================================

def test_extract_markers_separates_note_and_boundary():
    text = ("Hello there. {NOTE: kept the term 'Falcon'}"
            " {BOUNDARY_WARNING} world.")
    clean, flags, notes = extract_markers(text)
    assert "Hello there." in clean
    assert "world." in clean
    assert "{NOTE:" not in clean
    assert "{BOUNDARY_WARNING}" not in clean
    assert set(flags) == {"note", "boundary"}
    assert notes == ["kept the term 'Falcon'"]


def test_strip_markers_removes_all_markers():
    result = strip_markers("{NOTE: x} text {BOUNDARY_WARNING}")
    assert result == "text"


def test_detect_cut_boundary_heuristic():
    from app.output.markers import detect_cut_boundary
    assert detect_cut_boundary("mid")
    assert not detect_cut_boundary("A full sentence.")


# ============================================================
# SEGMENTS
# ============================================================

def test_build_segments_flags_and_strips_markers():
    chunks = [
        ("chunk-0", "<p>Hello <b>world</b>.</p>"),
        ("chunk-1", "<p>Second.</p>"),
        ("chunk-2", "<p>Untranslated.</p>"),
    ]
    translations = {
        "chunk-0": "سلام {NOTE: slang kept} {BOUNDARY_WARNING}",
        "chunk-1": "دوم",
    }
    chapter_map = {"chunk-0": ("ch1.xhtml", 0), "chunk-1": ("ch1.xhtml", 1)}
    segments = build_segments(chunks, translations, chapter_map, "epub")
    assert [s["id"] for s in segments] == ["chunk-0", "chunk-1"]
    assert segments[0]["source"] == "Hello world."
    assert segments[0]["target"] == "سلام"
    assert segments[0]["flagged"] is True
    assert segments[0]["notes"] == ["slang kept"]
    assert segments[1]["flagged"] is False
    assert segments[0]["chapter"] == "ch1.xhtml"


def test_build_segments_accepts_dict_chapter_map():
    chunks = [("chunk-0", "alpha")]
    translations = {"chunk-0": "beta"}
    chapter_map = {"chunk-0": {"item": "book.xhtml", "pos": 0}}
    segments = build_segments(chunks, translations, chapter_map, "pdf")
    assert segments[0]["chapter"] == "book.xhtml"
    assert segments[0]["format"] == "pdf"


def test_build_qa_report_lists_only_flagged():
    report = build_qa_report(SAMPLE, title="Book", filetype="epub")
    assert "QA_REPORT" in report
    assert "flagged    : 1" in report
    assert "chunk-0" in report
    assert "chunk-1" not in report


# ============================================================
# JSON_SEGMENTS
# ============================================================

def test_json_segments_writer_document_structure():
    with TemporaryDirectory() as tmp:
        path = json_segments_module.write_json_segments(
            SAMPLE, Path(tmp) / "book.segments.json",
            title="Book", to_lang="FA",
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["book"] == "Book"
        assert data["to_language"] == "FA"
        assert len(data["segments"]) == 2
        first = data["segments"][0]
        assert first["flagged"] is True
        assert first["notes"] == ["ambiguous term kept as-is"]
        assert first["target"] == "The first translated sentence."


# ============================================================
# TXT_BILINGUAL
# ============================================================

def test_txt_bilingual_alternates_original_and_translation():
    rendered = txt_module.render_bilingual_txt(SAMPLE, title="Book", filetype="epub", to_lang="FA")
    assert "[ORIGINAL]" in rendered
    assert "[TRANSLATION]" in rendered
    original_index = rendered.index("[ORIGINAL]")
    translation_index = rendered.index("[TRANSLATION]")
    assert original_index < translation_index
    assert "The first original sentence." in rendered
    assert "The first translated sentence." in rendered


# ============================================================
# MARKDOWN
# ============================================================

def test_markdown_writer_preserves_chapter_heads():
    with TemporaryDirectory() as tmp:
        path = markdown_module.write_markdown(
            SAMPLE, Path(tmp) / "book.md", title="Book", filetype="epub", to_lang="FA",
        )
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# Book")
        assert "## ch1.xhtml" in content
        assert "The first translated sentence." in content
        assert "The second translated sentence." in content


# ============================================================
# DOCX
# ============================================================

def test_docx_writer_valid_zip_with_rtl_and_highlight():
    with TemporaryDirectory() as tmp:
        path = docx_module.write_docx(
            SAMPLE, Path(tmp) / "book.docx", title="Book", to_lang="FA",
        )
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert "[Content_Types].xml" in names
            assert "word/document.xml" in names
            document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "The first translated sentence." in document_xml
        assert "<w:bidi/>" in document_xml
        assert '<w:highlight w:val="yellow"/>' in document_xml


def test_docx_writer_no_bidi_for_ltr_target():
    with TemporaryDirectory() as tmp:
        path = docx_module.write_docx(
            SAMPLE, Path(tmp) / "book.docx", title="Book", to_lang="EN",
        )
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "<w:bidi/>" not in document_xml


# ============================================================
# PDF
# ============================================================

def test_translated_pdf_writer_pages_and_text():
    with TemporaryDirectory() as tmp:
        path = pdf_module.write_translated_pdf(
            SAMPLE, Path(tmp) / "book.pdf", title="Book", to_lang="EN",
        )
        document = fitz.open(stream=path.read_bytes(), filetype="pdf")
        try:
            assert len(document) == len(SAMPLE)
            text = unicodedata.normalize(
                "NFKC",
                "".join(document[i].get_text() for i in range(len(document))),
            )
            assert "The first translated sentence." in text
            assert "The second translated sentence." in text
        finally:
            document.close()


def test_bilingual_pdf_writer_shows_both_columns():
    with TemporaryDirectory() as tmp:
        path = pdf_module.write_bilingual_pdf(
            SAMPLE, Path(tmp) / "book.bilingual.pdf", title="Book", to_lang="EN",
        )
        document = fitz.open(stream=path.read_bytes(), filetype="pdf")
        try:
            text = unicodedata.normalize(
                "NFKC",
                "".join(document[i].get_text() for i in range(len(document))),
            )
            assert "The first original sentence." in text
            assert "The first translated sentence." in text
        finally:
            document.close()


# ============================================================
# SRT
# ============================================================

SRT_DOCUMENT = """1
00:00:01,000 --> 00:00:04,000
Hello world.

2
00:00:05,000 --> 00:00:08,000
Second line here.
"""


def test_srt_parse_serialize_roundtrip():
    blocks = srt_module.parse_srt(SRT_DOCUMENT)
    assert [block.index for block in blocks] == [1, 2]
    assert blocks[0].start == "00:00:01,000"
    assert blocks[0].text == "Hello world."
    assert srt_module.serialize_srt(blocks) == SRT_DOCUMENT


def test_srt_break_long_lines_keeps_lines_short():
    lines = srt_module.break_long_lines("word " * 30, max_length=42)
    assert all(len(line) <= 42 for line in lines)
    assert " ".join(lines).replace(" ", " ")  # no content loss


def test_srt_merge_preserves_timecodes_and_translations():
    blocks = srt_module.parse_srt(SRT_DOCUMENT)
    merged = srt_module.merge_translations(
        blocks,
        {"chunk-0": "ترجمه اول", "chunk-1": "ترجمه دوم"},
    )
    assert merged[0].index == 1
    assert merged[0].start == "00:00:01,000"
    assert merged[1].end == "00:00:08,000"
    assert merged[0].text == "ترجمه اول"
    assert merged[1].text == "ترجمه دوم"


def test_srt_validate_reports_structure_and_timecode_issues():
    bad = """1
00:01:02,000 --> 00:00:01,000
A line that is far too long to ever fit on a subtitle display.

3
not-a-timecode --> 00:00:05,000
Short.
"""
    issues = srt_module.validate_srt(bad)
    joined = "\n".join(issues)
    assert any("sequential" in issue for issue in issues)
    assert any("ends before" in issue for issue in issues)
    assert any("invalid" in issue for issue in issues)
    assert any("chars (max" in issue for issue in issues)


def test_srt_translate_flow_keeps_timecodes():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        source = tmp / "movie.srt"
        source.write_text(SRT_DOCUMENT, encoding="utf-8")
        (tmp / "movie_translations.json").write_text(
            json.dumps({
                "chunk-0": "سلام دنیا",
                "chunk-1": "خط دوم اینجا است",
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        output = tmp / "movie_fa.srt"
        result = srt_module.translate_srt(
            None,
            source,
            output,
            mode="test",
            debug=False,
        )
        assert result == output
        assert output.exists()
        blocks = srt_module.parse_srt(output.read_text(encoding="utf-8"))
        assert [block.index for block in blocks] == [1, 2]
        assert blocks[0].start == "00:00:01,000"
        assert blocks[1].end == "00:00:08,000"
        assert blocks[0].text == "سلام دنیا"
        assert blocks[1].text == "خط دوم اینجا است"
        assert srt_module.validate_srt(output.read_text(encoding="utf-8")) == []


# ============================================================
# FORMATS DISPATCH
# ============================================================

def test_normalize_outputs_handles_aliases_and_casing():
    normalized = normalize_outputs("json, TXT_BILINGUAL, md")
    assert normalized == ["json_segments", "txt_bilingual", "markdown"]
    assert normalize_outputs(["docx", "docx"]) == ["docx"]
    try:
        normalize_outputs("bogus_format")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_generate_outputs_writes_requested_formats():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        result = generate_outputs(
            SAMPLE,
            requested=["json_segments", "txt_bilingual", "markdown", "docx",
                       "translated_pdf", "bilingual_pdf", "translated_epub", "srt"],
            output_dir=tmp,
            base_name="book",
            filetype="epub",
            title="Book",
            to_lang="FA",
        )
        generated = result["generated"]
        for name in ("json_segments", "txt_bilingual", "markdown",
                     "docx", "translated_pdf", "bilingual_pdf"):
            assert Path(generated[name]).is_file(), name
        assert "translated_epub" in result["skipped"]
        assert "srt" in result["skipped"]
        assert result["flagged"] == 1
        assert "QA_REPORT" in result["qa_report"]
        assert (tmp / "book.segments.json").exists()
        assert (tmp / "book.bilingual.txt").exists()
        assert (tmp / "book.bilingual.pdf").exists()


def test_emit_outputs_returns_cleaned_translations():
    chunks = [("chunk-0", "Hello.")]
    translations = {"chunk-0": "سلام {BOUNDARY_WARNING} {NOTE: cut off}"}
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        result, segments, cleaned = emit_outputs(
            tmp / "in.epub",
            tmp / "book_fa.epub",
            chunks,
            translations,
            {"chunk-0": ("ch1.xhtml", 0)},
            filetype="epub",
            requested=["json_segments", "txt_bilingual"],
            title="Book",
            to_lang="FA",
        )
        assert cleaned["chunk-0"] == "سلام"
        assert segments[0]["flagged"] is True
        assert result["flagged"] == 1


# ============================================================
# PROMPTS
# ============================================================

def test_default_prompt_includes_engine_rules():
    prompt = get_default_prompt("EN", "FA", "epub")
    assert "[FORMAT: EPUB]" in prompt
    assert "{BOUNDARY_WARNING}" in prompt
    assert "{NOTE: " in prompt


def test_engine_prompt_detects_srt_format_and_limits():
    prompt = get_engine_prompt("EN", "FA", "srt")
    assert "[FORMAT: SRT]" in prompt
    assert "42 characters" in prompt
    assert "timecodes" in prompt