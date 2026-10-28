import uuid

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework import status

from books_service.models import Book
from borrowings_service.models import Borrowing

from payments_service.models import Payment
from payments_service.serializers import PaymentDetailSerializer

PAYMENT_URL = reverse("payments_service:payment-list")
PAYMENT_SUCCESS_URL = reverse("payments_service:payment-success")
PAYMENT_CANCEL_URL = reverse("payments_service:payment-cancel")


def payment_detail_url(payment_id):
    return reverse("payments_service:payment-detail", args=[payment_id])


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


def sample_borrowing(user, **params):
    if "book" not in params:
        params["book"] = sample_book()
    if "expected_return_date" not in params:
        params["expected_return_date"] = timezone.localdate() + timedelta(
            days=1
        )

    return Borrowing.objects.create(user=user, **params)


def sample_payment(borrowing, **params):

    defaults = {
        "status": Payment.Status.PENDING,
        "payment_type": Payment.PaymentType.PAYMENT,
        "borrowing": borrowing,
        "session_url": "http://127.0.0.1/",
        "session_id": f"cs_test_{uuid.uuid4()}",
        "money_to_pay": Decimal("1.49"),
    }
    defaults.update(params)

    return Payment.objects.create(**defaults)


class UnauthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@user.com",
            password="password",
        )
        self.borrowing = sample_borrowing(self.user)
        self.payment = sample_payment(self.borrowing)

    def test_auth_required(self):

        url = payment_detail_url(self.payment.id)

        result_list = self.client.get(PAYMENT_URL)
        result_detail = self.client.get(url)

        self.assertEqual(result_list.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            result_detail.status_code, status.HTTP_401_UNAUTHORIZED
        )

    @patch("payments_service.views.stripe.checkout.Session.retrieve")
    def test_success_response_400_when_session_id_missing(
        self, mock_stripe_retrieve
    ):
        result = self.client.get(PAYMENT_SUCCESS_URL)

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            result.data["detail"], "The session id parameter is missing."
        )
        mock_stripe_retrieve.assert_not_called()

    @patch("payments_service.views.stripe.checkout.Session.retrieve")
    def test_success_response_400_when_session_id_not_found(
        self, mock_stripe_retrieve
    ):
        result = self.client.get(
            PAYMENT_SUCCESS_URL, {"session_id": "invalid"}
        )

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            result.data["detail"],
            "There is no payment session with this session_id.",
        )
        mock_stripe_retrieve.assert_not_called()

    @patch("payments_service.views.stripe.checkout.Session.retrieve")
    def test_success_when_payment_is_paid(self, mock_stripe_retrieve):
        mock_stripe_retrieve.return_value = {"payment_status": "paid"}

        result = self.client.get(
            PAYMENT_SUCCESS_URL, {"session_id": self.payment.session_id}
        )
        self.payment.refresh_from_db()

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(
            result.data["detail"],
            "Payment was successful! Thank you for your purchase!",
        )
        self.assertEqual(self.payment.status, Payment.Status.PAID)

    @patch("payments_service.views.stripe.checkout.Session.retrieve")
    def test_success_when_payment_is_already_paid(self, mock_stripe_retrieve):
        self.payment.status = Payment.Status.PAID
        self.payment.save(update_fields=["status"])
        mock_stripe_retrieve.return_value = {"payment_status": "paid"}

        result = self.client.get(
            PAYMENT_SUCCESS_URL, {"session_id": self.payment.session_id}
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data["detail"], "Your borrowing already paid!")

    @patch("payments_service.views.stripe.checkout.Session.retrieve")
    def test_success_when_payment_is_unpaid(self, mock_stripe_retrieve):
        mock_stripe_retrieve.return_value = {"payment_status": "unpaid"}

        result = self.client.get(
            PAYMENT_SUCCESS_URL, {"session_id": self.payment.session_id}
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(
            result.data["detail"],
            (
                "Payment has not been received yet. "
                "Please wait or try again later."
            ),
        )

    def test_cancel_response_400_when_session_id_missing(self):
        result = self.client.get(PAYMENT_CANCEL_URL)

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            result.data["detail"], "The session id parameter is missing."
        )

    def test_cancel_response_400_when_session_id_not_found(self):
        result = self.client.get(PAYMENT_CANCEL_URL, {"session_id": "invalid"})

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            result.data["detail"],
            "There is no payment session with this session_id.",
        )

    def test_cancel_when_payment_is_unpaid(self):
        result = self.client.get(
            PAYMENT_CANCEL_URL, {"session_id": self.payment.session_id}
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data["url"], self.payment.session_url)
        self.assertEqual(
            result.data["message"],
            (
                "You can pay later, the payment "
                "link is only available for 24 hours."
            ),
        )

    def test_cancel_when_payment_is_paid(self):
        self.payment.status = Payment.Status.PAID
        self.payment.save(update_fields=["status"])

        result = self.client.get(
            PAYMENT_CANCEL_URL, {"session_id": self.payment.session_id}
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data["detail"], "Your borrowing already paid!")


class AuthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = get_user_model().objects.create_user(
            email="user1@user.com",
            password="password",
        )
        self.user2 = get_user_model().objects.create_user(
            email="user2@user.com",
            password="password",
        )
        self.client.force_authenticate(self.user1)

        self.book_one = sample_book(title="One")
        self.borrowing_user1 = sample_borrowing(self.user1, book=self.book_one)
        self.payment_user1 = sample_payment(self.borrowing_user1)
        self.book_two = sample_book(title="Two")
        self.borrowing_user2 = sample_borrowing(self.user2, book=self.book_two)
        self.payment_user2 = sample_payment(
            self.borrowing_user2,
            session_url="http://0.0.0.0/",
        )

    def test_payment_list(self):
        result = self.client.get(PAYMENT_URL)

        payment_id = [payment["id"] for payment in result.data]

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertIn(self.payment_user1.id, payment_id)
        self.assertNotIn(self.payment_user2.id, payment_id)

    def test_payment_detail(self):
        url = payment_detail_url(self.payment_user1.id)
        result = self.client.get(url)

        serializer = PaymentDetailSerializer(self.payment_user1, many=False)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(
            result.data["session_url"], self.payment_user1.session_url
        )
        self.assertEqual(
            result.data["session_id"], self.payment_user1.session_id
        )
        self.assertEqual(
            result.data["borrowing_id"], self.payment_user1.borrowing_id
        )
        self.assertEqual(result.data["borrowing_book"], self.book_one.title)
        self.assertEqual(result.data["user_email"], self.user1.email)

        for key in result.data:
            self.assertEqual(result.data[key], serializer.data[key])

    def test_cannot_get_not_own_payment_detail(self):
        url = payment_detail_url(self.payment_user2.id)
        result = self.client.get(url)

        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_method_post_not_allowed_for_user(self):
        result = self.client.post(PAYMENT_URL)

        self.assertEqual(
            result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_payment_detail_unsafe_methods_not_allowed_for_user(self):
        unsafe_methods = ("put", "patch", "delete")
        url = payment_detail_url(self.payment_user1.id)

        for method in unsafe_methods:
            with self.subTest(method=method):
                result = getattr(self.client, method)(url)

                self.assertEqual(
                    result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )

    def test_payment_list_ordering(self):
        payment_user1_second = sample_payment(self.borrowing_user1)

        result = self.client.get(PAYMENT_URL)

        expected_list = [payment_user1_second.id, self.payment_user1.id]
        actual_list = [payment["id"] for payment in result.data]

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(expected_list, actual_list)


class AdminPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@admin.com", password="password", is_staff=True
        )
        self.client.force_authenticate(self.admin)

        self.user1 = get_user_model().objects.create_user(
            email="user1@user.com",
            password="password",
        )
        self.user2 = get_user_model().objects.create_user(
            email="user2@user.com",
            password="password",
        )

        self.book_one = sample_book(title="One")
        self.borrowing_user1 = sample_borrowing(self.user1, book=self.book_one)
        self.payment_user1 = sample_payment(self.borrowing_user1)
        self.book_two = sample_book(title="Two")
        self.borrowing_user2 = sample_borrowing(self.user2, book=self.book_two)
        self.payment_user2 = sample_payment(
            self.borrowing_user2,
            session_url="http://0.0.0.0/",
        )
        self.book_admin = sample_book(title="Admin")
        self.borrowing_admin = sample_borrowing(
            self.admin, book=self.book_admin
        )
        self.payment_admin = sample_payment(
            self.borrowing_admin,
            session_url="http://1.1.1.1/",
        )

    def test_admin_can_get_all_payments(self):
        result = self.client.get(PAYMENT_URL)

        payments_expected = Payment.objects.values_list("id", flat=True)
        payments_actual = [payment["id"] for payment in result.data]

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(list(payments_expected), payments_actual)

    def test_can_get_not_own_payment_detail(self):
        url = payment_detail_url(self.payment_user2.id)
        result = self.client.get(url)

        serializer = PaymentDetailSerializer(self.payment_user2, many=False)

        self.assertEqual(result.status_code, status.HTTP_200_OK)

        for key in result.data:
            self.assertEqual(serializer.data[key], result.data[key])

    def test_payment_method_post_not_allowed_for_admin(self):
        result = self.client.post(PAYMENT_URL)

        self.assertEqual(
            result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_payment_detail_unsafe_methods_not_allowed_for_admin(self):
        unsafe_methods = ("put", "patch", "delete")
        url = payment_detail_url(self.payment_user1.id)

        for method in unsafe_methods:
            with self.subTest(method=method):
                result = getattr(self.client, method)(url)

                self.assertEqual(
                    result.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )
