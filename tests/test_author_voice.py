from app.translation.prompts import AUTHOR_VOICE_MARKER, with_author_voice
from app.web import PAGE


def test_author_voice_guidance_preserves_concrete_style_signals():
    prompt = with_author_voice("Translate accurately.")
    assert AUTHOR_VOICE_MARKER in prompt
    assert "sentence rhythm" in prompt
    assert "narrative point of view" in prompt
    assert "character's dialogue" in prompt
    assert "humor, irony, ambiguity" in prompt


def test_author_voice_guidance_is_idempotent():
    prompt = with_author_voice("Translate accurately.")
    assert with_author_voice(prompt) == prompt


def test_workspace_exposes_author_voice_control():
    assert 'name="preserve_voice"' in PAGE
    assert "حفظ لحن و صدای نویسنده" in PAGE
