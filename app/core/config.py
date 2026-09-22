from pathlib import Path

import yaml


# ============================================================
# Project Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"


# ============================================================
# Load Configuration
# ============================================================

def read_config():
    """
    Load application configuration from config.yaml.

    The configuration file is expected to contain settings
    such as API credentials and translation configuration.

    Returns:
        dict: Application configuration.

    Raises:
        FileNotFoundError:
            If config.yaml does not exist.

        ValueError:
            If the configuration file is empty or invalid.
    """

    try:

        with CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            config = yaml.safe_load(f)

        if config is None:

            raise ValueError(
                "Configuration file is empty."
            )

        if not isinstance(config, dict):

            raise ValueError(
                "Configuration file must contain "
                "a YAML dictionary."
            )

        return config

    except FileNotFoundError:

        print(
            f"Error: {CONFIG_FILE} not found.\n"
            "Please create config/config.yaml "
            "with your API configuration."
        )

        print(
            "\nExample config.yaml content:\n"
            "\n"
            "openai:\n"
            "  api_key: 'your-api-key-here'\n"
            "  base_url: 'https://api.gapgpt.app/v1'\n"
            "\n"
            "translation:\n"
            "  default_model: 'gpt-5.6-luna'\n"
            "  default_from_lang: 'EN'\n"
            "  default_to_lang: 'FA'\n"
            "  default_mode: 'fast'\n"
            "  temperature: 0.2\n"
            "  max_retries: 5\n"
            "  retry_delay: 5\n"
            "  max_retry_delay: 60"
        )

        raise

    except yaml.YAMLError as e:

        raise ValueError(
            f"Could not parse {CONFIG_FILE}.\n"
            f"YAML error: {e}"
        ) from e


# ============================================================
# OpenAI Configuration
# ============================================================

def get_openai_config():
    """
    Return OpenAI-compatible API configuration.

    Returns:
        dict:
            {
                "api_key": "...",
                "base_url": "..."
            }
    """

    config = read_config()

    openai_config = config.get("openai")

    if not openai_config:

        raise ValueError(
            "Missing 'openai' section in config.yaml."
        )

    api_key = openai_config.get("api_key")

    if not api_key:

        raise ValueError(
            "Missing 'openai.api_key' in config.yaml."
        )

    base_url = openai_config.get("base_url")

    if not base_url:

        raise ValueError(
            "Missing 'openai.base_url' in config.yaml."
        )

    return {
        "api_key": api_key,
        "base_url": base_url
    }


# ============================================================
# Translation Configuration
# ============================================================

def get_translation_config():
    """
    Return translation configuration.

    Returns:
        dict: Translation settings.
    """

    config = read_config()

    translation_config = config.get(
        "translation",
        {}
    )

    return translation_config
