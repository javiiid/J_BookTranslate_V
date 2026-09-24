# ============================================================
# Style Preset Manager Tests
# ============================================================

import json
import tempfile
from pathlib import Path

import pytest

from app.presets.manager import (
    load_preset,
    get_presets,
    get_preset_names,
    build_style_prompt,
    get_preset_params,
    detect_style,
    build_preset_system_message,
    PRESETS_FILE,
)


class TestLoadPreset:
    def test_literary_defaults(self):
        preset = load_preset("literary")
        assert preset["name"] == "ادبی"
        assert preset["name_en"] == "Literary"
        params = preset["params"]
        assert params["temperature"] == 0.7
        assert params["top_p"] == 0.9
        assert params["presence_penalty"] == 0.3

    def test_technical_defaults(self):
        preset = load_preset("technical")
        assert preset["name"] == "فنی"
        assert preset["name_en"] == "Technical"
        params = preset["params"]
        assert params["temperature"] == 0.2
        assert params["top_p"] == 0.85

    def test_conversational_defaults(self):
        preset = load_preset("conversational")
        assert preset["name"] == "محاوره‌ای"
        assert preset["name_en"] == "Conversational"
        params = preset["params"]
        assert params["temperature"] == 0.6

    def test_formal_defaults(self):
        preset = load_preset("formal")
        assert preset["name"] == "رسمی"
        assert preset["name_en"] == "Formal"
        params = preset["params"]
        assert params["temperature"] == 0.3

    def test_unknown_falls_back(self):
        preset = load_preset("nonexistent")
        assert preset["name"] == "ادبی"

    def test_returns_dict_with_params(self):
        preset = load_preset("literary")
        assert "params" in preset
        assert "prompt_insert" in preset
        assert "recommended_for" in preset


class TestGetPresets:
    def test_returns_all(self):
        presets = get_presets()
        assert set(presets.keys()) == {"literary", "technical", "conversational", "formal"}

    def test_get_names(self):
        names = get_preset_names()
        assert names == ["literary", "technical", "conversational", "formal"]


class TestBuildStylePrompt:
    def test_literary_has_prompt(self):
        prompt = build_style_prompt("literary")
        assert "[STYLE: LITERARY]" in prompt
        assert len(prompt) > 100

    def test_technical_has_prompt(self):
        prompt = build_style_prompt("technical")
        assert "[STYLE: TECHNICAL]" in prompt

    def test_empty_for_unknown(self):
        # Unknown styles fall back to literary, not empty
        prompt = build_style_prompt("nonexistent")
        assert "[STYLE: LITERARY]" in prompt

    def test_none_returns_literary(self):
        prompt = build_style_prompt(None)
        assert "[STYLE: LITERARY]" in prompt


class TestGetPresetParams:
    def test_returns_params_dict(self):
        params = get_preset_params("literary")
        assert isinstance(params, dict)
        assert "temperature" in params
        assert "top_p" in params
        assert "presence_penalty" in params
        assert "frequency_penalty" in params

    def test_defaults_when_style_none(self):
        params = get_preset_params(None)
        assert isinstance(params, dict)
        assert "temperature" in params
        assert params["temperature"] == 0.7  # literary default

    def test_all_params_present(self):
        for style in ["literary", "technical", "conversational", "formal"]:
            params = get_preset_params(style)
            for key in ["temperature", "top_p", "presence_penalty", "frequency_penalty"]:
                assert key in params, f"{key} missing in {style}"


class TestDetectStyle:
    def test_literary_detection(self):
        text = "The wind whispered secrets through the ancient oaks. A melancholy soul wandered."
        assert detect_style(text) == "literary"

    def test_technical_detection(self):
        text = "To initialize the database, run npm run migrate. The API endpoint returns JSON."
        assert detect_style(text) == "technical"

    def test_conversational_detection(self):
        text = "Getting started is super easy. Just download the app and you're good to go!"
        result = detect_style(text)
        assert result in ["conversational", "literary"]

    def test_formal_detection(self):
        text = "The committee has reviewed your application and will notify you within 10 business days."
        assert detect_style(text) == "formal"

    def test_empty_returns_literary(self):
        assert detect_style("") == "literary"


class TestBuildPresetSystemMessage:
    def test_appends_style(self):
        base = "You are a translator."
        result = build_preset_system_message(base, "literary")
        assert "[STYLE: LITERARY]" in result
        assert base in result

    def test_no_style_returns_literary(self):
        # None means default = literary
        base = "You are a translator."
        result = build_preset_system_message(base, None)
        assert "[STYLE: LITERARY]" in result
        assert base in result

    def test_empty_prompt_returns_literary(self):
        # nonexistent style falls back to literary
        base = "You are a translator."
        result = build_preset_system_message(base, "nonexistent")
        assert "[STYLE: LITERARY]" in result

    def test_prompt_appended_once(self):
        base = "Base message"
        result = build_preset_system_message(base, "technical")
        assert result.count("[STYLE: TECHNICAL]") == 1


class TestStylesJsonStructure:
    def test_styles_file_exists(self):
        assert PRESETS_FILE.exists()

    def test_valid_json(self):
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        assert "literary" in data
        assert "technical" in data
        assert "conversational" in data
        assert "formal" in data

    def test_each_preset_has_required_keys(self):
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        for key, preset in data.items():
            assert "name" in preset, f"{key} missing name"
            assert "name_en" in preset, f"{key} missing name_en"
            assert "params" in preset, f"{key} missing params"
            assert "prompt_insert" in preset, f"{key} missing prompt_insert"
            for p in ["temperature", "top_p", "presence_penalty", "frequency_penalty"]:
                assert p in preset["params"], f"{key} missing {p}"
