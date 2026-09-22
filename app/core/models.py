# ============================================================
# Model Configuration
# ============================================================

DEFAULT_MODEL = "gpt-5.6-luna"


SUPPORTED_MODELS = {
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