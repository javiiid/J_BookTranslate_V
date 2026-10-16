# ============================================================
# Output registry unification: one truth, every surface matches.
# ============================================================

import re
from pathlib import Path

import pytest

from app.output.convert import normalize_convert_formats
from app.output.formats import (
    CALIBRATION_OUTPUTS,
    CONVERT_OUTPUTS,
    OUTPUT_FORMATS,
    TRANSLATION_OUTPUTS,
    normalize_outputs,
)

REPO = Path(__file__).parents[1]


def test_translation_outputs_excludes_primary_epub():
    assert "translated_epub" in OUTPUT_FORMATS  # still known for back-compat
    assert "translated_epub" not in TRANSLATION_OUTPUTS
    assert TRANSLATION_OUTPUTS == {
        "json_segments", "txt_bilingual", "markdown", "docx",
        "translated_pdf", "mobile_pdf", "bilingual_pdf",
        "srt", "quality_report",
    }
    # normalize still accepts the primary name (maps to skipped)
    assert "translated_epub" in normalize_outputs(["translated_epub"])


def test_calibration_outputs_rejects_srt_and_quality():
    assert CALIBRATION_OUTPUTS == TRANSLATION_OUTPUTS - {"srt", "quality_report"}
    # mirrors CalibrationService.create rejection set
    assert not (CALIBRATION_OUTPUTS & {"srt", "quality_report"})


def test_convert_outputs_subset_and_normalizer():
    assert CONVERT_OUTPUTS == {
        "json_segments", "txt_bilingual", "markdown",
        "docx", "translated_pdf",
    }
    assert CONVERT_OUTPUTS < TRANSLATION_OUTPUTS
    assert normalize_convert_formats(["docx", "pdf"]) == ["docx", "translated_pdf"]
    # bilingual has no meaning without a translation: same engine
    assert normalize_convert_formats("bilingual_pdf") == ["translated_pdf"]
    for bad in ("srt", "quality_report", "translated_epub", "bilingual", "mobile_pdf"):
        with pytest.raises(ValueError):
            normalize_convert_formats(bad)


def test_legacy_web_form_offers_srt():
    import app.web as web

    for name in sorted(TRANSLATION_OUTPUTS):
        assert f'value="{name}"' in web.PAGE, name


def test_react_surfaces_match_python_registry():
    workspace = (REPO / "frontend/ui/src/pages/WorkspacePage.tsx").read_text(encoding="utf-8")
    offered_ws = set(re.findall(r"\['(\w+)'", workspace))
    assert CALIBRATION_OUTPUTS <= offered_ws, CALIBRATION_OUTPUTS - offered_ws
    assert "mobile_pdf" in offered_ws  # 7th workshop row
    assert not (offered_ws & {"srt", "quality_report"})

    conversion = (REPO / "frontend/ui/src/lib/conversion.ts").read_text(encoding="utf-8")
    offered_conv = set(re.findall(r"id: '(\w+)'", conversion))
    assert offered_conv == CONVERT_OUTPUTS
