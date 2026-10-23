from django.utils import timezone

from celery import shared_task
from celery_once import QueueOnce
from requests.exceptions import RequestException

from borrowings_service.models import Borrowing
from notifications_service.services import telegram_message


@shared_task(
    name="notify_admin_via_telegram",
    autoretry_for=(RequestException,),
    retry_kwargs={"max_retries": 3},
    rate_limit="18/m",
)
def notify_admin_via_telegram(message: str):
    telegram_message(message)


@shared_task(
    name="notify_overdue_borrowings_daily",
    base=QueueOnce,
    once={"timeout": 120},
)
def notify_overdue_borrowings_daily():
    overdue_borrowings = Borrowing.objects.select_related(
        "book", "user"
    ).filter(
        expected_return_date__lte=timezone.localdate(),
        actual_return_date__isnull=True,
    )

    if overdue_borrowings.count() == 0:
        telegram_message("No borrowings overdue today!")
        return

    for borrowing in overdue_borrowings:
        delayed = timezone.localdate() - borrowing.expected_return_date
        message = (
            f"⚠️ Overdue Borrowing (Delayed by {delayed.days} days)\n\n"
            f"👤 User: {borrowing.user}\n"
            f"📘 Book: «{borrowing.book.title}» — {borrowing.book.author}\n"
            f"📅 Borrow Date: {borrowing.borrow_date}\n"
            f"📅 Expected Return: {borrowing.expected_return_date}\n"
        )
        notify_admin_via_telegram.delay(message)
