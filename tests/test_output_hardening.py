# ============================================================
# Output P0 hardening: ZWNJ, per-format isolation, SRT cleanup
# ============================================================

from pathlib import Path

from app.output import generate_outputs
from app.output.segments import _html_to_text, build_qa_report, build_segments


def test_html_to_text_preserves_zwnj():
    assert _html_to_text("<p>test</p>") == "test"
    assert "\u200c" in _html_to_text("<p>A\u200cB</p>")
    # spaces/tabs still collapse
    assert _html_to_text("<p>a   b</p>") == "a b"


def test_build_segments_preserves_zwnj():
    chunks = [("chunk-0", "<p>A\u200cB</p>")]
    translations = {"chunk-0": "C\u200cD"}
    segments = build_segments(chunks, translations, {}, "epub")
    assert segments[0]["source"] == "A\u200cB"
    assert segments[0]["target"] == "C\u200cD"


def test_per_format_isolation(monkeypatch, tmp_path):
    import app.output.formats as formats

    def _boom(*args, **kwargs):
        raise RuntimeError("docx exploded")

    monkeypatch.setattr(formats.docx, "write_docx", _boom)
    segments = [
        {
            "id": "chunk-0", "position": 0,
            "source": "Hello.", "target": "Hello FA.",
            "format": "epub", "chapter": "ch1.xhtml",
            "flagged": False, "notes": [],
        }
    ]
    result = generate_outputs(
        segments,
        requested=["json_segments", "docx", "markdown"],
        output_dir=tmp_path,
        base_name="book",
        filetype="epub",
        title="Book",
        to_lang="FA",
    )
    assert "docx" in result["skipped"]
    assert "exploded" in result["skipped"]["docx"]
    assert Path(result["generated"]["json_segments"]).is_file()
    assert Path(result["generated"]["markdown"]).is_file()
    # no half-written docx left behind
    assert not (tmp_path / "book.docx").exists()


def test_srt_validation_failure_leaves_no_file(monkeypatch, tmp_path):
    import app.output.srt as srt_module

    monkeypatch.setattr(srt_module, "validate_srt", lambda text: ["ends before it starts"])
    segments = [
        {
            "id": "chunk-0", "position": 0,
            "source": "Hello world.", "target": "Hello FA world.",
            "format": "epub", "chapter": "ch1.xhtml",
            "flagged": False, "notes": [],
        }
    ]
    result = generate_outputs(
        segments,
        requested=["srt"],
        output_dir=tmp_path,
        base_name="book",
        filetype="epub",
        title="Book",
        to_lang="FA",
    )
    assert "srt" in result["skipped"]
    assert "srt" not in result["generated"]
    assert not (tmp_path / "book.srt").exists()


def test_malformed_segments_do_not_crash(tmp_path):
    segments = [
        {"id": "chunk-0", "position": 0, "source": "a", "target": "b",
         "format": "epub", "chapter": "ch1"},
        # missing flagged/notes/quality keys entirely
        {"id": "chunk-1", "position": 1, "source": "c", "target": "d",
         "format": "epub", "chapter": "ch1"},
    ]
    report = build_qa_report(segments, title="Book", filetype="epub")
    assert "flagged    : 0" in report
    result = generate_outputs(
        segments,
        requested=["json_segments", "txt_bilingual"],
        output_dir=tmp_path,
        base_name="book",
        filetype="epub",
        title="Book",
        to_lang="FA",
    )
    assert "json_segments" in result["generated"]
    assert result["flagged"] == 0
