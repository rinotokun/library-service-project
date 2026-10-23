from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException, HTTPError

from notifications_service.services import telegram_message


@override_settings(
    GROUP_ID=-1234567890,
    URL_SEND_MESSAGE="https://api.telegram.org/bot-token/sendMessage",
)
class TelegramMessageTests(SimpleTestCase):

    @patch("notifications_service.services.requests.post")
    def test_send_valid_request_success(self, mock_requests_post):
        telegram_message("message")

        mock_requests_post.assert_called_once_with(
            settings.URL_SEND_MESSAGE,
            json={"chat_id": settings.GROUP_ID, "text": "message"},
            timeout=5,
        )

    @patch(
        "notifications_service.services.requests.post",
        side_effect=RequestException,
    )
    def test_network_error_is_raised(self, mock_requests_post):
        with self.assertRaises(RequestException):
            telegram_message("message")

    @patch(
        "notifications_service.services.requests.post",
    )
    def test_telegram_error_handling(self, mock_requests_post):
        mock_requests_post.return_value.raise_for_status.side_effect = (
            HTTPError
        )

        with self.assertRaises(HTTPError):
            telegram_message("message")
