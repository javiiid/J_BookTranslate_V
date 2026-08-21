from app.core.client import create_client
from app.core.config import get_translation_config


def main():

    print("=" * 60)
    print("Testing API Client")
    print("=" * 60)

    config = get_translation_config()

    model = config.get(
        "default_model"
    )

    print(f"Model: {model}")

    client = create_client()

    print("API client initialized.")
    print("Sending test request...")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "سلام! فقط بگو: اتصال موفق بود."
            }
        ]
    )

    result = response.choices[0].message.content

    print("\nAPI Response:")
    print(result)

    print("\n" + "=" * 60)
    print("Client test completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()