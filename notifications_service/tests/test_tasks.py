from unittest.mock import patch

from django.test import SimpleTestCase

from notifications_service.tasks import notify_admin_via_telegram


class NotifyAdminTaskTests(SimpleTestCase):

    @patch("notifications_service.tasks.telegram_message")
    def test_notify_admin_via_telegram_for_correct_work(
        self, mock_telegram_message
    ):
        notify_admin_via_telegram("message")

        mock_telegram_message.assert_called_once_with(
            "message"
        )
