from celery import shared_task
from requests.exceptions import RequestException

from notifications_service.services import telegram_message


@shared_task(
    name="notify_admin_via_telegram",
    autoretry_for=(RequestException,),
    retry_kwargs={"max_retries": 3},
)
def notify_admin_via_telegram(message: str):
    telegram_message(message)
