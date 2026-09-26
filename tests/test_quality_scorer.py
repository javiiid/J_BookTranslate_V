# ============================================================
# Chunk Quality Scorer Tests
# ============================================================

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.pipeline.quality_scorer import (
    ChunkScore,
    composite_score,
    build_scorer_prompt,
    make_scorer,
    parse_scorer_response,
    rule_format_score,
    rule_boundary_score,
    rule_length_score,
    rule_terminology_score,
    score_chunk,
    score_and_attach,
    build_qa_report,
    write_quality_report,
    summary_from_segments,
    wants_quality,
    resolve_mode,
    length_out_of_range,
    length_ratio_value,
)

from app.output.segments import build_segments
from app.output.formats import generate_outputs, normalize_outputs


# ── helpers ────────────────────────────────────────────

def fake_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ],
    )


def client_with(content):
    client = Mock()
    client.chat.completions.create.return_value = (
        fake_response(content)
    )
    return client


def glossary_snapshot(terms=None):
    if terms is None:
        terms = []
    return {"version": "1", "terms": terms}


SINGLE_CHUNK = [("chunk-0", "<p>The Falcon flies.</p>")]
SINGLE_TRANSLATION = {"chunk-0": "<p>The صقر flies.</p>"}

GLOSSARY = glossary_snapshot(
    [{"source_term": "Falcon", "target_term": "صقر"}]
)

LLM_FULL = json.dumps({
    "chunk_id": "chunk-0",
    "scores": {
        "accuracy": 8.0, "fluency": 7.0,
        "terminology": 9.0,
        "format_preservation": 8.0,
        "boundary_integrity": 7.0,
        "length_ratio": 6.0,
    },
    "composite": 7.7,
    "flagged": False,
    "flag_reasons": [],
    "notes": "",
})

LLM_LIGHT = json.dumps({
    "chunk_id": "chunk-0",
    "scores": {"accuracy": 5.0, "fluency": 6.0},
    "flagged": True,
    "flag_reasons": ["accuracy < 6"],
    "notes": "",
})


# ── ChunkScore ─────────────────────────────────────────

def test_chunk_score_from_dict_full():
    data = {
        "chunk_id": "c1",
        "scores": {
            "accuracy": 8.0, "fluency": 7.0,
            "terminology": 9.0,
            "format_preservation": 8.0,
            "boundary_integrity": 7.0,
            "length_ratio": 6.0,
        },
        "composite": 7.7,
        "flagged": False,
        "flag_reasons": [],
    }
    score = ChunkScore.from_dict(data)
    assert score.chunk_id == "c1"
    assert score.flagged is False
    assert score.composite == pytest.approx(7.7)


def test_chunk_score_computed_not_trusted():
    """Composite is recomputed from weights, ignoring the model's value."""
    data = {
        "chunk_id": "c2",
        "scores": {"accuracy": 5.0, "fluency": 5.0},
        "composite": 99.0,  # wrong — must be recomputed
        "flagged": True,
        "flag_reasons": [],
    }
    score = ChunkScore.from_dict(data)
    assert score.composite == pytest.approx(5.0)
    assert score.flagged is True  # accuracy < 6


def test_chunk_score_clamps_and_ignores_unknown():
    data = {
        "chunk_id": "c3",
        "scores": {
            "accuracy": 15.0,  # clamped to 10
            "fluency": -3.0,   # clamped to 0
            "unknown_dim": 5.0,
        },
        "composite": 0.0,
        "flagged": False,
        "flag_reasons": [],
    }
    score = ChunkScore.from_dict(data)
    assert score.scores["accuracy"] == 10.0
    assert score.scores["fluency"] == 0.0
    assert "unknown_dim" not in score.scores


def test_chunk_score_as_storage():
    score = ChunkScore(
        chunk_id="c1",
        scores={"accuracy": 8.0, "fluency": 7.0, "terminology": None,
                "format_preservation": 8.0,
                "boundary_integrity": 7.0, "length_ratio": 6.0},
        composite=7.45,
        flagged=True,
        flag_reasons=["accuracy < 6"],
        notes="a note",
    )
    storage = score.as_storage()
    assert storage["composite"] == 7.45
    assert storage["notes"] == "a note"
    assert "accuracy" in storage["scores"]


# ── composite_score ────────────────────────────────────

def test_composite_all_dims():
    scores = {
        "accuracy": 8.0, "fluency": 7.0, "terminology": 9.0,
        "format_preservation": 8.0, "boundary_integrity": 7.0,
        "length_ratio": 6.0,
    }
    # 8*.30 + 7*.25 + 9*.15 + 8*.15 + 7*.10 + 6*.05
    expected = 8 * .30 + 7 * .25 + 9 * .15 + 8 * .15 + 7 * .10 + 6 * .05
    assert composite_score(scores) == pytest.approx(round(expected, 2))


def test_composite_terminology_redistributed():
    scores = {
        "accuracy": 8.0, "fluency": 7.0,
        "format_preservation": 8.0, "boundary_integrity": 7.0,
        "length_ratio": 6.0,
    }
    # terminology null -> .15 redistributed to acc (.30) and flu (.25)
    w_acc = .30 + .15 * .30 / .55
    w_flu = .25 + .15 * .25 / .55
    expected = (
        w_acc * 8 + w_flu * 7 + .15 * 8 + .10 * 7 + .05 * 6
    )
    assert composite_score(scores) == pytest.approx(round(expected, 2))


def test_composite_empty():
    assert composite_score({}) == 0.0


# ── rule-based scorers ─────────────────────────────────────────

def test_rule_format_missing_tags():
    source = "<p>a<b>b</b></p>"
    target = "<p>a</p>"  # lost <b>b</b>
    assert rule_format_score(source, target) <= 5.0


def test_rule_format_intact():
    source = "<p>a<b>b</b></p>"
    target = "<p>a<b>b</b></p>"
    assert rule_format_score(source, target) == 10.0


def test_rule_format_no_structure():
    assert rule_format_score("plain", "plain") == 10.0


def test_rule_boundary_clean():
    assert rule_boundary_score("The sentence is complete.") == 10.0


def test_rule_boundary_cut_start():
    # starts lowercase -> mid-sentence start
    assert rule_boundary_score("continuation after break.") == 5.0


def test_rule_boundary_cut_both():
    assert rule_boundary_score("lowercase start") == 2.0


def test_rule_length_within_range():
    assert rule_length_score(1.1, 0.9, 1.4) == 10.0


def test_rule_length_out_of_range():
    assert rule_length_score(2.0, 0.9, 1.4) in (1.0, 2.0)
    assert length_out_of_range(2.0, 0.9, 1.4) is True


def test_rule_length_slightly_outside():
    assert rule_length_score(1.55, 0.9, 1.4) == 7.0


def test_rule_terminology_no_glossary():
    assert rule_terminology_score("x", "y", {}) is None


def test_rule_terminology_respects_glossary():
    glossary = glossary_snapshot(
        [{"source_term": "Falcon", "target_term": "صقر"}]
    )
    # source has Falcon, translation has صقر -> 10
    assert (
        rule_terminology_score(
            "The Falcon flies",
            "The صقر flies",
            glossary,
        )
        == 10.0
    )
    # source has Falcon, translation lacks صقر -> low
    assert (
        rule_terminology_score(
            "The Falcon flies",
            "The bird flies",
            glossary,
        )
        < 6.0
    )


# ── prompt building ────────────────────────────────────

def test_build_scorer_prompt_has_tokens():
    prompt = build_scorer_prompt(
        chunk_id="c1",
        source_text="<p>Hello</p>",
        translated_text="<p>سلام</p>",
        source_lang="EN",
        target_lang="FA",
    )
    assert "{{chunk_id}}" not in prompt
    assert "<p>Hello</p>" in prompt
    assert "سلام" in prompt


def test_build_scorer_light_prompt():
    prompt = build_scorer_prompt(
        chunk_id="c1",
        source_text="x",
        translated_text="y",
        source_lang="EN",
        target_lang="FA",
        mode="light",
    )
    assert "Score ONLY two dimensions" in prompt
    assert "format_preservation" not in prompt


# ── parse_scorer_response ──────────────────────────────

def test_parse_scorer_response_fenced():
    content = (
        "```json\n"
        '{"chunk_id":"c1","scores":{"accuracy":8.0,"fluency":7.0,'
        '"terminology":null,"format_preservation":8.0,'
        '"boundary_integrity":7.0,"length_ratio":6.0},'
        '"composite":7.7,"flagged":false,"flag_reasons":[],"notes":""}\n'
        "```"
    )
    score = parse_scorer_response(content, chunk_id="c1")
    assert score.chunk_id == "c1"
    assert score.scores["accuracy"] == 8.0
    assert score.flagged is False


def test_parse_scorer_response_prose():
    content = (
        'The result: {"chunk_id":"c1","scores":'
        '{"accuracy":5.0,"fluency":6.0,"terminology":null,'
        '"format_preservation":9.0,"boundary_integrity":8.0,'
        '"length_ratio":7.0},'
        '"composite":6.5,"flagged":true,'
        '"flag_reasons":["accuracy < 6"],"notes":""} done.'
    )
    score = parse_scorer_response(content, chunk_id="c1")
    assert score.chunk_id == "c1"
    assert score.scores["accuracy"] == 5.0
    assert score.flagged is True


def test_parse_scorer_response_empty_raises():
    with pytest.raises(ValueError):
        parse_scorer_response("")


# ── score_chunk ────────────────────────────────────────

def test_score_chunk_rules_mode_no_client():
    score = score_chunk(
        chunk_id="c1",
        source_text="<p>The Falcon flies.</p>",
        translated_text="<p>The bird flies.</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=None,
    )
    assert score.mode == "rules"
    assert score.scores["accuracy"] is None
    assert score.scores["fluency"] is None
    assert score.scores["format_preservation"] is not None
    assert score.scores["boundary_integrity"] is not None
    assert score.scores["length_ratio"] is not None
    assert isinstance(score.composite, float)


def test_score_chunk_boundary_warning_deduction():
    score = score_chunk(
        chunk_id="c1",
        source_text="<p>The sentence is complete.</p>",
        translated_text=(
            "<p>The sentence is complete. {BOUNDARY_WARNING}</p>"
        ),
        source_lang="EN",
        target_lang="FA",
        llm_client=None,
    )
    assert score.scores["boundary_integrity"] < 10.0
    assert any(
        r == "{BOUNDARY_WARNING} present"
        for r in score.flag_reasons
    )


def test_score_chunk_note_flag():
    score = score_chunk(
        chunk_id="c1",
        source_text="<p>Hello.</p>",
        translated_text=(
            "<p>{NOTE: kept term} Hello.</p>"
        ),
        source_lang="EN",
        target_lang="FA",
        llm_client=None,
    )
    assert any(r == "{NOTE:} present" for r in score.flag_reasons)


def test_score_chunk_length_ratio_flag():
    # very long translation for a short source -> out of range for EN->FA
    score = score_chunk(
        chunk_id="c1",
        source_text="<p>Hi.</p>",
        translated_text="<p>" + "a" * 500 + "</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=None,
    )
    assert any(
        r.startswith("length ratio outside")
        for r in score.flag_reasons
    )


def test_score_chunk_llm_full_mode():
    score = score_chunk(
        chunk_id="chunk-0",
        source_text="<p>The Falcon flies.</p>",
        translated_text="<p>The صقر flies.</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        mode="full",
        glossary=GLOSSARY,
    )
    assert score.scores["accuracy"] == 8.0
    assert score.scores["fluency"] == 7.0
    assert score.scores["terminology"] == 9.0
    assert score.flagged is False


def test_score_chunk_llm_light_mode():
    score = score_chunk(
        chunk_id="chunk-0",
        source_text="<p>The Falcon flies.</p>",
        translated_text="<p>The صقر flies.</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=client_with(LLM_LIGHT),
        model="gpt-5.6-terra",
        mode="light",
        glossary=GLOSSARY,
    )
    assert score.scores["accuracy"] == 5.0
    assert score.scores["fluency"] == 6.0
    assert score.scores["terminology"] == 10.0  # rule-based: term present
    assert any("accuracy" in r for r in score.flag_reasons)


def test_score_chunk_llm_failure_falls_back():
    client = Mock()
    client.chat.completions.create.side_effect = RuntimeError(
        "API down"
    )
    score = score_chunk(
        chunk_id="chunk-0",
        source_text="<p>The Falcon flies.</p>",
        translated_text="<p>The صقر flies.</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=client,
        model="gpt-5.6-terra",
        glossary=GLOSSARY,
    )
    assert score.flagged is True
    assert any(
        "scorer error" in r for r in score.flag_reasons
    )


def test_score_chunk_no_glossary_terminology_null():
    score = score_chunk(
        chunk_id="chunk-0",
        source_text="<p>Hello</p>",
        translated_text="<p>سلام</p>",
        source_lang="EN",
        target_lang="FA",
        llm_client=client_with(LLM_FULL),
        glossary=None,
    )
    assert score.scores["terminology"] is None


# ── score_and_attach ───────────────────────────────────

def test_score_and_attach_attaches_quality():
    scorer = make_scorer(
        ["json_segments", "quality_report"],
        client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        source_lang="EN",
        target_lang="FA",
        all_chunks=SINGLE_CHUNK,
        translations=SINGLE_TRANSLATION,
        glossary=GLOSSARY,
    )
    segments = build_segments(
        SINGLE_CHUNK,
        SINGLE_TRANSLATION,
        filetype="epub",
    )
    scores = score_and_attach(segments, scorer)
    assert len(scores) == 1
    assert segments[0]["quality"]["composite"] == pytest.approx(7.7)
    assert "quality" in segments[0]


def test_score_and_attach_parallel():
    scorer = make_scorer(
        ["quality_report"],
        client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        source_lang="EN",
        target_lang="FA",
        all_chunks=SINGLE_CHUNK,
        translations=SINGLE_TRANSLATION,
        max_workers=2,
        glossary=GLOSSARY,
    )
    segments = build_segments(
        SINGLE_CHUNK,
        SINGLE_TRANSLATION,
        filetype="epub",
    )
    scores = score_and_attach(segments, scorer)
    assert len(scores) == 1
    assert segments[0]["quality"]["composite"] == pytest.approx(7.7)


# ── build_qa_report ────────────────────────────────────

def test_build_qa_report_summary():
    from app.pipeline.quality_scorer import ChunkScore
    scores = [
        ChunkScore(
            chunk_id="c1",
            scores={"accuracy": 8.0, "fluency": 7.0, "terminology": None,
                    "format_preservation": 8.0,
                    "boundary_integrity": 7.0, "length_ratio": 6.0},
            composite=7.45,
            flagged=False,
            flag_reasons=[],
        ),
        ChunkScore(
            chunk_id="c2",
            scores={"accuracy": 5.0, "fluency": 6.0, "terminology": None,
                    "format_preservation": 4.0,
                    "boundary_integrity": 3.0, "length_ratio": 8.0},
            composite=4.2,
            flagged=True,
            flag_reasons=["composite below 6.5", "format preservation below 5"],
        ),
    ]
    report = build_qa_report(scores)
    assert report["total_chunks"] == 2
    assert report["flagged_count"] == 1
    assert report["average_composite"] == pytest.approx(
        round((7.45 + 4.2) / 2, 2)
    )
    assert len(report["flagged_chunks"]) == 1
    assert report["flagged_chunks"][0]["chunk_id"] == "c2"


# ── write_quality_report ───────────────────────────────

def test_write_quality_report_structure():
    scorer = make_scorer(
        ["quality_report"],
        client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        source_lang="EN",
        target_lang="FA",
        all_chunks=SINGLE_CHUNK,
        translations=SINGLE_TRANSLATION,
        glossary=GLOSSARY,
    )
    segments = build_segments(
        SINGLE_CHUNK,
        SINGLE_TRANSLATION,
        filetype="epub",
    )
    score_and_attach(segments, scorer)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "book.quality.json"
        write_quality_report(
            segments, path, title="Book", filetype="epub", to_lang="FA",
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["book"] == "Book"
        assert data["to_language"] == "FA"
        assert len(data["segments"]) == 1
        seg = data["segments"][0]
        assert seg["id"] == "chunk-0"
        assert "quality" in seg
        assert seg["quality"]["composite"] == pytest.approx(7.7)
        assert "summary" in data


# ── summary_from_segments ──────────────────────────────────

def test_summary_from_segments():
    segments = [
        {
            "id": "c1",
            "quality": {
                "composite": 7.7,
                "flag_reasons": [],
                "scores": {"accuracy": 8.0, "fluency": 7.0,
                           "terminology": 9.0,
                           "format_preservation": 8.0,
                           "boundary_integrity": 7.0,
                           "length_ratio": 6.0},
                "notes": "",
            },
        },
        {
            "id": "c2",
            "quality": {
                "composite": 4.2,
                "flag_reasons": ["composite below 6.5"],
                "scores": {},
                "notes": "",
            },
        },
    ]
    summary = summary_from_segments(segments)
    assert summary["total_chunks"] == 2
    assert summary["flagged_count"] == 1
    assert summary["average_composite"] == pytest.approx(5.95)


def test_summary_from_segments_none():
    assert summary_from_segments([]) is None


# ── wants_quality ──────────────────────────────────────

def test_wants_quality():
    assert wants_quality(["quality_report"]) is True
    assert wants_quality(["json_segments"]) is False
    assert wants_quality("quality_report,markdown") is True
    assert wants_quality("json_segments") is False


# ── make_scorer ────────────────────────────────────────

def test_make_scorer_returns_none_when_not_requested():
    scorer = make_scorer(["json_segments"])
    assert scorer is None


def test_make_scorer_loads_glossary():
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job"
        job_dir.mkdir()
        (job_dir / "glossary.json").write_text(
            json.dumps({
                "source_language": "EN",
                "target_language": "FA",
                "terms": [
                    {"source_term": "Falcon", "target_term": "صقر"},
                ],
            }),
            encoding="utf-8",
        )
        scorer = make_scorer(
            ["quality_report"],
            client=Mock(),
            model="gpt-5.6-terra",
            source_lang="EN",
            target_lang="FA",
            paths={"job_dir": str(job_dir)},
        )
        assert scorer is not None
        assert scorer["glossary"].get("terms")


def test_make_scorer_chunks_map():
    scorer = make_scorer(
        ["quality_report"],
        all_chunks=[("a", "x"), ("b", "y")],
        translations={"a": "x'", "b": "y'"},
    )
    assert scorer["chunks"] == {"a": "x", "b": "y"}
    assert scorer["translations"] == {"a": "x'", "b": "y'"}


# ── resolve_mode ───────────────────────────────────────

def test_resolve_mode_no_client_rules():
    assert resolve_mode("full", client=None) == "rules"


def test_resolve_mode_explicit():
    assert resolve_mode("light", client=Mock()) == "light"


# ── generate_outputs integration ───────────────────────

def test_generate_outputs_quality_report():
    scorer = make_scorer(
        ["json_segments", "quality_report"],
        client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        source_lang="EN",
        target_lang="FA",
        all_chunks=SINGLE_CHUNK,
        translations=SINGLE_TRANSLATION,
        glossary=GLOSSARY,
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        result = generate_outputs(
            build_segments(
                SINGLE_CHUNK,
                SINGLE_TRANSLATION,
                filetype="epub",
            ),
            requested=["json_segments", "quality_report"],
            output_dir=out,
            base_name="book",
            filetype="epub",
            title="Book",
            to_lang="FA",
            scorer=scorer,
        )
        assert "quality_report" in result["generated"]
        quality_path = Path(result["generated"]["quality_report"])
        data = json.loads(quality_path.read_text(encoding="utf-8"))
        assert "quality" in data["segments"][0]
        assert result["quality"] is not None
        assert result["quality"]["total_chunks"] == 1


def test_generate_outputs_quality_skipped_without_scorer():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        result = generate_outputs(
            [
                {
                    "id": "c1",
                    "source": "x",
                    "target": "y",
                    "format": "epub",
                    "chapter": "ch1",
                    "flagged": False,
                    "notes": [],
                }
            ],
            requested=["quality_report"],
            output_dir=out,
            base_name="book",
            filetype="epub",
            title="Book",
            to_lang="FA",
            scorer=None,
        )
        assert "quality_report" in result["skipped"]


def test_emit_outputs_scorer_param():
    from app.output.formats import emit_outputs
    scorer = make_scorer(
        ["quality_report"],
        client=client_with(LLM_FULL),
        model="gpt-5.6-terra",
        source_lang="EN",
        target_lang="FA",
        all_chunks=SINGLE_CHUNK,
        translations=SINGLE_TRANSLATION,
        glossary=GLOSSARY,
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.segments.json"
        result = emit_outputs(
            input_path=Path("in.epub"),
            output_path=out,
            all_chunks=SINGLE_CHUNK,
            translations=SINGLE_TRANSLATION,
            chapter_map={},
            filetype="epub",
            requested=["quality_report"],
            scorer=scorer,
        )
        assert "quality_report" in result[0]["generated"]


# ── prompt rendering determinism ───────────────────────

def test_scorer_prompt_uses_template_tokens():
    prompt = build_scorer_prompt(
        chunk_id="c1",
        source_text="<p>Hello</p>",
        translated_text="<p>سلام</p>",
        source_lang="EN",
        target_lang="FA",
    )
    # no unreplaced double-brace tokens
    assert "{{" not in prompt
    # chunk values present
    assert "c1" in prompt
    assert "<p>Hello</p>" in prompt
    assert "سلام" in prompt


# ── length ratio helpers ───────────────────────────────

def test_length_ratio_value():
    ratio = length_ratio_value(
        "<p>Hello world</p>",
        "<p>سلام دنیا</p>",
    )
    assert ratio is not None
    assert 0.5 < ratio < 2.0


def test_length_ratio_empty_source():
    assert length_ratio_value("", "<p>x</p>") is None


# ── normalization aliases ──────────────────────────────

def test_normalize_outputs_accepts_quality_report():
    assert "quality_report" in normalize_outputs(
        ["quality_report", "json_segments"]
    )
