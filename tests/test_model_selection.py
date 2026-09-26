"""Tests for single-sourced model selection.

The user's report was "the model is set to luna but terra is sent". The cause
was six function signatures defaulting to "gpt-5.6-terra" in a hardcoded
string, plus a translation form that carried its own two-option list which
disagreed with config.yaml. These tests pin the fix: config decides, the form
is generated from SUPPORTED_MODELS, and an unknown model is refused at submit
rather than at the first paid chunk.
"""
import inspect
import sys
from pathlib import Path

import pytest

from app.core.models import (
    DEFAULT_MODEL,
    SUPPORTED_MODELS,
    is_supported_model,
    resolve_default_model,
)

APP = Path(r"D:\J_BookTranslate_V\app")


# --------------------------------------------------------------------------
# The reported bug: terra defaults baked into signatures
# --------------------------------------------------------------------------

def _signature_defaults(module_name, function_name):
    sys.path.insert(0, r"D:\J_BookTranslate_V")
    module = __import__(module_name, fromlist=["_"])
    target = module
    # Walk dotted parts so a class method can be inspected too; taking the
    # signature of the class would report __init__, not the method.
    for part in function_name.split("."):
        target = getattr(target, part)
    return {
        name: parameter.default
        for name, parameter in inspect.signature(target).parameters.items()
    }


@pytest.mark.parametrize("module_name,function_name", [
    ("app.pipeline.pipeline", "translate"),
    ("app.translation.translator", "translate_chunk"),
    ("app.translation.translator", "process_translations"),
    ("app.translation.batch", "batch_translate_chunks"),
    ("app.pipeline.pdf_handler", "PDFHandler"),
])
def test_no_module_hardcodes_terra_as_a_default(module_name, function_name):
    """A function default is invisible at the call site, so it must not name a model.

    If any of these go back to a literal model string, a caller that omits
    `model` silently overrides the user again.
    """
    source_file = APP / Path(*module_name.split(".")[1:]).with_suffix(".py")
    if not source_file.is_file():
        source_file = APP / (module_name.split(".")[-1] + ".py")
    text = source_file.read_text(encoding="utf-8")
    offenders = [
        line.strip() for line in text.splitlines()
        if "gpt-5.6-terra" in line and not line.strip().startswith(('"', "'", "#"))
    ]
    assert not offenders, f"{source_file.name} still hardcodes terra: {offenders}"


def test_translate_resolves_an_omitted_model_from_config():
    defaults = _signature_defaults("app.pipeline.pipeline", "translate")
    assert defaults["model"] is None, "an omitted model must reach the resolver"


def test_translate_chunk_resolves_an_omitted_model():
    defaults = _signature_defaults("app.translation.translator", "translate_chunk")
    assert defaults["model"] is None


def test_transcribe_pdf_accepts_a_model_instead_of_hardcoding_one():
    """The PDF vision step is the one that silently billed terra for every file."""
    defaults = _signature_defaults("app.pipeline.pdf_handler", "PDFHandler.transcribe_pdf")
    assert "model" in defaults, "transcribe_pdf must take a model parameter"
    assert defaults["model"] is None


# --------------------------------------------------------------------------
# Config is the single source of truth
# --------------------------------------------------------------------------

def test_resolver_prefers_config(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.read_config_safe",
        lambda: {"translation": {"default_model": "gpt-5.6-terra"}},
    )
    assert resolve_default_model() == "gpt-5.6-terra"


def test_resolver_falls_back_when_config_is_silent(monkeypatch):
    monkeypatch.setattr("app.core.config.read_config_safe", lambda: {"translation": {}})
    assert resolve_default_model() == DEFAULT_MODEL


def test_resolver_ignores_a_model_the_code_does_not_know(monkeypatch):
    """A typo must not reach the provider; it costs a paid run to discover."""
    monkeypatch.setattr(
        "app.core.config.read_config_safe",
        lambda: {"translation": {"default_model": "gpt-5.6-trebra"}},
    )
    assert resolve_default_model() == DEFAULT_MODEL


def test_resolver_survives_a_broken_config(monkeypatch):
    def explode():
        raise OSError("config.yaml is gone")
    monkeypatch.setattr("app.core.config.read_config_safe", explode)
    assert resolve_default_model() == DEFAULT_MODEL


def test_resolver_ignores_a_non_string_config_value(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.read_config_safe",
        lambda: {"translation": {"default_model": 42}},
    )
    assert resolve_default_model() == DEFAULT_MODEL


def test_the_resolved_default_is_always_supported():
    assert is_supported_model(resolve_default_model())


# --------------------------------------------------------------------------
# The form is generated, not hand-written
# --------------------------------------------------------------------------

def test_the_translation_form_offers_every_supported_model():
    import re

    import app.web as web
    block = re.search(r'<select name="model"[^>]*>.*?</select>', web.PAGE, re.S).group(0)
    offered = set(re.findall(r'<option value="([^"]+)"', block))
    assert offered == set(SUPPORTED_MODELS), (
        f"the dropdown offers {sorted(offered)}, code knows {sorted(SUPPORTED_MODELS)}"
    )


def test_all_three_models_are_known():
    assert set(SUPPORTED_MODELS) == {
        "gpt-5.6-terra", "gpt-5.6-luna", "gemini-3.1-flash-lite",
    }


# --------------------------------------------------------------------------
# The dropdown is stamped per request, not baked into the template
# --------------------------------------------------------------------------

def _stamped(configured):
    import app.web as web
    original = web.resolve_default_model
    web.resolve_default_model = lambda: configured
    try:
        return web.model_select_html(web.PAGE)
    finally:
        web.resolve_default_model = original


def _model_select(html):
    import re
    block = re.search(r'<select name="model"[^>]*>.*?</select>', html, re.S).group(0)
    return block


def _selected_values(html, name):
    import re
    block = re.search(rf'<select name="{name}"[^>]*>.*?</select>', html, re.S)
    if not block:
        return []
    return [
        value for value, attrs in re.findall(r'<option value="([^"]+)"([^>]*)>', block.group(0))
        if "selected" in attrs
    ]


def test_the_dropdown_follows_config_without_a_restart():
    """The original bug: the form said luna, the pipeline sent terra.

    Baking the choice into the template meant config.yaml had no effect until
    someone edited the file by hand, so the two could disagree indefinitely.
    """
    for configured in sorted(SUPPORTED_MODELS):
        html = _stamped(configured)
        assert _selected_values(html, "model") == [configured], (
            f"config says {configured} but the form preselects "
            f"{_selected_values(html, 'model')}"
        )


def test_exactly_one_model_option_is_ever_selected():
    for configured in sorted(SUPPORTED_MODELS):
        assert len(_selected_values(_stamped(configured), "model")) == 1


def test_stamping_does_not_disturb_the_other_dropdowns():
    """A page-wide rewrite would silently change what the mode form submits.

    The mode, language and output dropdowns each carry their own preselected
    option. Those must come out identical no matter which model is configured.
    """
    baseline = _stamped(sorted(SUPPORTED_MODELS)[0])
    for configured in sorted(SUPPORTED_MODELS):
        html = _stamped(configured)
        for name in ("mode", "from_lang", "to_lang"):
            assert _selected_values(html, name) == _selected_values(baseline, name), (
                f"the {name} dropdown changed when the model config changed to {configured}"
            )


def test_every_supported_model_still_appears_after_stamping():
    html = _stamped("gpt-5.6-luna")
    block = _model_select(html)
    for model in SUPPORTED_MODELS:
        assert f'value="{model}"' in block, f"{model} vanished from the dropdown"


def test_the_page_is_not_mutated_between_requests():
    """Stamping must not write back into the shared template."""
    import app.web as web
    before = web.PAGE
    _stamped("gpt-5.6-terra")
    assert web.PAGE is before, "model_select_html must return a new string"


def test_the_template_bakes_in_no_selection():
    """config.yaml must be the only place a preselection can come from.

    A `selected` attribute left in the template is a trap: it reads as if the
    choice were configured, but the stamp overwrites it at request time, so
    anyone serving the raw template gets the stale value instead.
    """
    import app.web as web
    assert "selected" not in _model_select(web.PAGE), (
        "the model select still carries a baked selected attribute"
    )


def test_the_model_select_is_present_exactly_once():
    import re

    import app.web as web
    blocks = re.findall(r'<select name="model"[^>]*>.*?</select>', web.PAGE, re.S)
    assert len(blocks) == 1, f"expected one model dropdown, found {len(blocks)}"


def test_support_check_rejects_an_unknown_model():
    assert is_supported_model("gpt-5.6-luna")
    assert not is_supported_model("gpt-5.6-luna-typo")
    assert not is_supported_model("")
