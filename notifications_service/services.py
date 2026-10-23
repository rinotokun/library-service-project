import requests

from django.conf import settings


def telegram_message(message: str) -> None:
    payload = {
        "chat_id": settings.GROUP_ID,
        "text": message
    }

    response = requests.post(
        settings.URL_SEND_MESSAGE,
        json=payload,
        timeout=5
    )
    response.raise_for_status()
