# ============================================================
# Model Configuration
# ============================================================

DEFAULT_MODEL = "gpt-5.6-luna"


def resolve_default_model():
    """Return the model a run should use when the caller names none.

    config.yaml wins over the code default so the account settings page
    and the pipeline cannot drift apart. An unknown value falls back to
    DEFAULT_MODEL rather than being sent to the provider, because a typo
    here would otherwise fail on the first chunk of a paid run.

    A missing or unreadable config also falls back rather than raising: this
    is called at the top of a run, and a broken config should not stop a
    translation that could still proceed on the compiled-in default.
    """
    try:
        from app.core.config import read_config_safe

        configured = (read_config_safe().get("translation") or {}).get("default_model")
    except (OSError, AttributeError, TypeError, ValueError):
        return DEFAULT_MODEL
    if isinstance(configured, str) and configured.strip() in SUPPORTED_MODELS:
        return configured.strip()
    return DEFAULT_MODEL


SUPPORTED_MODELS = {
    "gpt-5.6-terra": {
        "provider": "openai-compatible",
        "description": "High-quality translation model",
    },
    "gpt-5.6-luna": {
        "provider": "openai-compatible",
        "description": "Primary translation model",
    },
    "gemini-3.1-flash-lite": {
        "provider": "openai-compatible",
        "description": "Fast, lower-cost translation model",
    },
}


def is_supported_model(model):
    """
    Check whether the requested model is supported.

    Parameters:
        model: Model name.

    Returns:
        bool: True if the model is supported,
              otherwise False.
    """

    return model in SUPPORTED_MODELS


def get_model_config(model):
    """
    Return configuration for the requested model.

    Parameters:
        model: Model name.

    Returns:
        dict: Configuration of the requested model.

    Raises:
        ValueError: If the model is not supported.
    """

    if not is_supported_model(model):

        raise ValueError(
            f"Unsupported model: {model}"
        )

    return SUPPORTED_MODELS[model]


def get_default_model():
    """
    Return the default translation model.

    Returns:
        str: Default model name.
    """

    return DEFAULT_MODEL
