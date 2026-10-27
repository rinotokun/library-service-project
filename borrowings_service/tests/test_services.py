from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from books_service.models import Book

from borrowings_service.models import Borrowing
from borrowings_service.services import create_checkout_session
from payments_service.models import Payment


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


class CreateCheckoutSessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@user.com",
            password="password",
        )

        self.book_one = sample_book(title="One")
        self.borrowing = sample_borrowing(
            self.user,
            book=self.book_one,
            expected_return_date=timezone.localdate() + timedelta(days=3)
        )

    @patch("borrowings_service.services.stripe.checkout.Session.create")
    def test_create_payment(self, mock_stripe_checkout_session_create):
        mock_stripe_checkout_session_create.return_value = {
            "url": "http://stripe-session",
            "id": "id_stripe_session",
        }

        create_checkout_session(self.borrowing)

        payment = Payment.objects.last()

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.payment_type, Payment.PaymentType.PAYMENT)
        self.assertEqual(payment.borrowing, self.borrowing)
        self.assertEqual(payment.session_url, "http://stripe-session")
        self.assertEqual(payment.session_id, "id_stripe_session")
        self.assertEqual(payment.money_to_pay, Decimal("4.47"))

        mock_stripe_checkout_session_create.assert_called_once()

        expected_kwargs = {
            "mode": "payment",
            "line_items": [
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": 447,
                        "product_data": {"name": self.borrowing.book.title},
                    },
                    "quantity": 1,
                }
            ],
            "success_url": (
                "http://127.0.0.1:8000/?session_id={CHECKOUT_SESSION_ID}"
            ),
        }
        actual_kwargs = mock_stripe_checkout_session_create.call_args.kwargs

        self.assertIsInstance(
            actual_kwargs["line_items"][0]["price_data"]["unit_amount"],
            int,
        )
        self.assertEqual(expected_kwargs, actual_kwargs)
