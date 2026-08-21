# ============================================================
# Core Configuration Test
# ============================================================

from app.core.config import read_config
from app.core.models import (
    DEFAULT_MODEL,
    SUPPORTED_MODELS,
    is_supported_model,
    get_model_config,
    get_default_model,
)
from app.core.client import create_client


def main():

    print("=" * 60)
    print("J Book Translate - Core Test")
    print("=" * 60)

    # ========================================================
    # 1. Configuration
    # ========================================================

    print("\n[1/5] Testing configuration...")

    config = read_config()

    if not isinstance(config, dict):
        raise TypeError(
            "Configuration must be a dictionary."
        )

    print("✓ Configuration loaded successfully.")

    # --------------------------------------------------------
    # Check OpenAI configuration
    # --------------------------------------------------------

    if "openai" not in config:
        raise ValueError(
            "Missing 'openai' section in config.yaml."
        )

    openai_config = config["openai"]

    if "api_key" not in openai_config:
        raise ValueError(
            "Missing 'api_key' in config.yaml."
        )

    if not openai_config["api_key"]:
        raise ValueError(
            "API key is empty."
        )

    print("✓ OpenAI configuration exists.")
    print("✓ API key exists.")

    # ========================================================
    # 2. Model Configuration
    # ========================================================

    print("\n[2/5] Testing model configuration...")

    print(
        f"Default model: {DEFAULT_MODEL}"
    )

    if DEFAULT_MODEL != "gpt-5.6-terra":
        raise AssertionError(
            f"Unexpected default model: {DEFAULT_MODEL}"
        )

    print("✓ Default model is correct.")

    if not SUPPORTED_MODELS:
        raise ValueError(
            "SUPPORTED_MODELS is empty."
        )

    print(
        f"✓ Supported models: "
        f"{list(SUPPORTED_MODELS.keys())}"
    )

    # ========================================================
    # 3. Model Validation
    # ========================================================

    print("\n[3/5] Testing model validation...")

    if not is_supported_model(
        DEFAULT_MODEL
    ):
        raise AssertionError(
            "Default model is not marked as supported."
        )

    print(
        f"✓ {DEFAULT_MODEL} is supported."
    )

    model_config = get_model_config(
        DEFAULT_MODEL
    )

    if not isinstance(model_config, dict):
        raise TypeError(
            "Model configuration must be a dictionary."
        )

    print(
        f"✓ Model configuration: "
        f"{model_config}"
    )

    # ========================================================
    # 4. Default Model Helper
    # ========================================================

    print("\n[4/5] Testing default model helper...")

    default_model = get_default_model()

    if default_model != DEFAULT_MODEL:
        raise AssertionError(
            "get_default_model() does not "
            "match DEFAULT_MODEL."
        )

    print(
        f"✓ get_default_model() → "
        f"{default_model}"
    )

    # ========================================================
    # 5. API Client Creation
    # ========================================================

    print("\n[5/5] Testing API client creation...")

    client = create_client()

    if client is None:
        raise RuntimeError(
            "create_client() returned None."
        )

    print("✓ API client initialized.")

    # ========================================================
    # IMPORTANT
    # ========================================================

    print()
    print("=" * 60)
    print("NO API REQUEST WAS SENT.")
    print("NO TOKENS WERE CONSUMED.")
    print("=" * 60)

    print()
    print("CORE TEST PASSED ✓")

    print()
    print("System status:")
    print("  Configuration : OK")
    print("  Model config  : OK")
    print("  Model         :", DEFAULT_MODEL)
    print("  Model support : OK")
    print("  API client    : OK")
    print("  API request   : NOT SENT")

    print("=" * 60)


if __name__ == "__main__":
    main()