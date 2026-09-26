from pathlib import Path

import os
from urllib.parse import urlparse

import yaml


# ============================================================
# Project Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"

# ============================================================
# Single source of truth for the API base URL
# ============================================================
# Every part of the app (CLI, web dashboard, account settings
# page, health check, translation engine) must resolve the
# base URL through config.yaml. This constant is only used as
# a fallback/default when config.yaml has no value yet.
DEFAULT_BASE_URL = "https://api.gapgpt.app/v1"


# ============================================================
# Concurrency ceiling
# ============================================================
# Single source of truth for the parallel translation limit. The translator
# clamps to it, the web API validates against it, and the account settings page
# reports it, so raising the ceiling is a one-line change.
#
# 12 simultaneous chat completions is already aggressive for a single provider
# account. Going higher without a matching tier usually just buys HTTP 429s,
# which cost a round trip plus backoff each time. Raise
# ``requests_per_minute`` in config.yaml first and let the adaptive limiter
# find the real ceiling.
MAX_TRANSLATION_CONCURRENCY = 12


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


def read_config_safe():
    """
    Same as ``read_config`` but never raises: returns an empty
    dict when config.yaml is missing, empty, or invalid. Used by
    code paths (like the dashboard) that must keep working even
    before the user has configured anything yet.
    """

    try:

        return read_config()

    except (FileNotFoundError, ValueError):

        return {}


def write_config(config):
    """
    Persist ``config`` back to config.yaml, creating the
    ``config/`` directory if it does not exist yet.

    This is the single write path every part of the app must go
    through when it needs to change the API configuration, so
    that the CLI, the web dashboard, and the account settings
    page always agree on one base URL.
    """

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    temporary = CONFIG_FILE.with_suffix(".yaml.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        temporary.replace(CONFIG_FILE)
    finally:
        if temporary.exists():
            temporary.unlink()


def normalize_base_url(value):
    """Normalize and validate an OpenAI-compatible API base URL."""
    base_url = str(value or "").strip()
    if not base_url:
        return DEFAULT_BASE_URL
    if "://" not in base_url:
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL باید یک آدرس معتبر با http یا https باشد.")
    if parsed.hostname == "api.gapgpt.app" and not parsed.path.rstrip("/").endswith("/v1"):
        base_url += "/v1"
    return base_url


def update_openai_config(base_url=None, api_key=None):
    """
    Update the ``openai`` section of config.yaml in place and
    return the resulting section.

    ``base_url`` and ``api_key`` are only overwritten when a
    truthy value is passed in, so callers can update just one of
    them (e.g. the dashboard's "test connection" form, which
    lets the user leave the API key blank to keep the existing
    one). If no base URL has ever been set, it defaults to
    ``DEFAULT_BASE_URL`` so every part of the app converges on
    the same address instead of drifting apart.
    """

    config = read_config_safe()

    openai_config = dict(config.get("openai") or {})

    if base_url:

        openai_config["base_url"] = normalize_base_url(base_url)

    elif not openai_config.get("base_url"):

        openai_config["base_url"] = DEFAULT_BASE_URL

    if api_key:

        openai_config["api_key"] = api_key

    config["openai"] = openai_config

    write_config(config)

    return openai_config


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

    base_url = normalize_base_url(openai_config.get("base_url") or DEFAULT_BASE_URL)

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
