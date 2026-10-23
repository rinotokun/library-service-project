from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.utils import timezone

from books_service.models import Book
from borrowings_service.models import Borrowing
from notifications_service.tasks import (
    notify_admin_via_telegram,
    notify_overdue_borrowings,
)


def sample_book(**params):
    defaults = {
        "title": "Harry Potter and the Philosopher's Stone",
        "author": "Joanne Rowling",
        "cover": Book.Cover.HARD,
        "inventory": 5,
        "daily_fee": Decimal("1.49"),
    }
    defaults.update(params)

    return Book.objects.create(**defaults)


def sample_borrowing(user, **param):
    if "book" not in param:
        param["book"] = sample_book()
    if "expected_return_date" not in param:
        param["expected_return_date"] = timezone.localdate() + timedelta(
            days=1
        )

    return Borrowing.objects.create(user=user, **param)


class NotifyAdminTaskTests(SimpleTestCase):

    @patch("notifications_service.tasks.telegram_message")
    def test_notify_admin_via_telegram_for_correct_work(
        self, mock_telegram_message
    ):
        notify_admin_via_telegram("message")

        mock_telegram_message.assert_called_once_with("message")


class NotifyOverdueBorrowingsTaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@user.com",
            password="password",
        )
        self.book_one = sample_book(title="One", inventory=10)
        self.book_two = sample_book(title="Two", inventory=10)

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_when_db_empty(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        notify_overdue_borrowings()

        mock_telegram_message.assert_called_once_with(
            "No borrowings overdue today!"
        )
        mock_notify_via_telegram.delay.assert_not_called()

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_when_db_with_no_overdue_borrowings(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        sample_borrowing(self.user)
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=2),
            expected_return_date=timezone.localdate() - timedelta(days=1),
            actual_return_date=timezone.localdate(),
        )
        notify_overdue_borrowings()

        mock_telegram_message.assert_called_once_with(
            "No borrowings overdue today!"
        )
        mock_notify_via_telegram.delay.assert_not_called()

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_when_db_with_overdue_borrowings_today(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=2),
            expected_return_date=timezone.localdate(),
        )
        notify_overdue_borrowings()

        mock_telegram_message.assert_not_called()
        mock_notify_via_telegram.delay.assert_called_once()

        message = mock_notify_via_telegram.delay.call_args.args[0]
        self.assertIn("(Delayed by 0 days)", message)

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_when_db_with_overdue_borrowings_in_past(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() - timedelta(days=2),
        )
        notify_overdue_borrowings()

        mock_telegram_message.assert_not_called()
        mock_notify_via_telegram.delay.assert_called_once()

        message = mock_notify_via_telegram.delay.call_args.args[0]
        self.assertIn("(Delayed by 2 days)", message)

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_when_db_with_few_overdue_borrowings_in_past(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() - timedelta(days=2),
        )
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() - timedelta(days=3),
        )
        sample_borrowing(
            self.user,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() + timedelta(days=2),
        )
        notify_overdue_borrowings()

        mock_telegram_message.assert_not_called()
        self.assertEqual(mock_notify_via_telegram.delay.call_count, 2)

    @patch("notifications_service.tasks.notify_admin_via_telegram")
    @patch("notifications_service.tasks.telegram_message")
    def test_notification_overdue_borrowings_message(
        self, mock_telegram_message, mock_notify_via_telegram
    ):
        borrow_date = timezone.localdate() - timedelta(days=5)
        expected_return_date = timezone.localdate() - timedelta(days=2)
        sample_borrowing(
            self.user,
            borrow_date=borrow_date,
            expected_return_date=expected_return_date,
            book=self.book_one,
        )
        notify_overdue_borrowings()

        mock_telegram_message.assert_not_called()
        message = mock_notify_via_telegram.delay.call_args.args[0]
        self.assertIn(self.user.email, message)
        self.assertIn(self.book_one.title, message)
        self.assertIn(self.book_one.author, message)
        self.assertIn(borrow_date.strftime("%Y-%m-%d"), message)
        self.assertIn(expected_return_date.strftime("%Y-%m-%d"), message)
