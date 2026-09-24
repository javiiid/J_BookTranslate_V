# ============================================================
# app/presets/manager.py
# ============================================================
"""
Style Preset Manager.

Loads and manages translation style presets (literary, technical,
conversational, formal). Each preset controls LLM parameters
(temperature, top_p, penalties) and style-specific prompt instructions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import read_config_safe

PRESETS_FILE = Path(__file__).parent / "styles.json"

# ── cache ──────────────────────────────────────────────

_PRESETS: dict | None = None


def _load_presets() -> dict:
    """Load presets from styles.json (cached)."""
    global _PRESETS
    if _PRESETS is not None:
        return _PRESETS
    try:
        data = json.loads(
            PRESETS_FILE.read_text(encoding="utf-8")
        )
        _PRESETS = data
        return _PRESETS
    except Exception:
        return {}


# ── public API ─────────────────────────────────────────

def load_preset(style: str | None = None) -> dict:
    """
    Return the preset dict for `style`.
    Defaults to the configured default style or 'literary'.
    """
    presets = _load_presets()
    if style is None:
        style = (
            (read_config_safe().get("translation") or {})
            .get("style_preset", "literary")
        )
    return presets.get(style, presets.get("literary", {}))


def get_presets() -> dict:
    """Return all presets."""
    return _load_presets()


def get_preset_names() -> list[str]:
    """Return preset keys."""
    return list(_load_presets().keys())


def build_style_prompt(style: str | None = None) -> str:
    """
    Return the style-specific prompt insert for the given style.
    Empty string when the preset has no prompt_insert.
    """
    preset = load_preset(style)
    return preset.get("prompt_insert", "") or ""


def get_preset_params(style: str | None = None) -> dict:
    """
    Return the LLM parameter override dict for the given style.
    Keys: temperature, top_p, presence_penalty, frequency_penalty.
    """
    preset = load_preset(style)
    return dict(preset.get("params", {}))


def detect_style(sample_text: str) -> str:
    """
    Heuristic style detection from a text sample.
    Returns the preset key (literary, technical, conversational, formal).
    """
    text = sample_text.lower()
    literary_indicators = [
        r'\b(whispered|ancient|eternal|melancholy|radiant|serene|gloomy)\b',
        r'\b(metaphor|symbol|allegory|imagery)\b',
        r'\b(soul|spirit|heart|dream|memory)\b',
    ]
    technical_indicators = [
        r'\b(api|endpoint|json|database|server|function|parameter|algorithm)\b',
        r'\b(initialize|configure|execute|implement|compile)\b',
        r'\b(version|release|deployment|architecture)\b',
    ]
    conversational_indicators = [
        r'\b(got|cool|hey|wow|really|just|like|pretty)\b',
        r'\b(awesome|fantastic|super|easy|simple)\b',
        r'\b(you know|trust me|honestly|believe me)\b',
    ]
    formal_indicators = [
        r'\b(committee|application|reviewed|officially|shall|within|decision)\b',
        r'\b(respectfully|submitted|approved|regarding|hereby)\b',
        r'\b(mandatory|required|compliance|regulations)\b',
    ]
    scores = {"literary": 0, "technical": 0, "conversational": 0, "formal": 0}
    for indicator in literary_indicators:
        if re.search(indicator, text):
            scores["literary"] += 1
    for indicator in technical_indicators:
        if re.search(indicator, text):
            scores["technical"] += 1
    for indicator in conversational_indicators:
        if re.search(indicator, text):
            scores["conversational"] += 1
    for indicator in formal_indicators:
        if re.search(indicator, text):
            scores["formal"] += 1
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "literary"


# ── preset-aware system prompt builder ─────────────────

def build_preset_system_message(
    base_message: str,
    style: str | None = None,
) -> str:
    """
    Append style-specific instructions to the base system message.
    """
    style_prompt = build_style_prompt(style)
    if not style_prompt:
        return base_message
    return base_message.rstrip() + "\n\n" + style_prompt
