from openai import OpenAI

from app.core.config import get_openai_config


def create_client():
    """
    Create an OpenAI-compatible API client.

    The API configuration is loaded from config/config.yaml.

    Returns:
        OpenAI: Configured API client.
    """

    config = get_openai_config()

    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"]
    )

    return client