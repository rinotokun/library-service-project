from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework import status

from books_service.models import Book
from borrowings_service.models import Borrowing

from payments_service.models import Payment
from payments_service.serializers import PaymentDetailSerializer

DUMMY_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
}


PAYMENT_URL = reverse("payments_service:payment-list")


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
        "session_id": "cs_test_12345",
        "money_to_pay": Decimal("1.49"),
    }
    defaults.update(params)

    return Payment.objects.create(**defaults)


@override_settings(CACHES=DUMMY_CACHE)
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


@override_settings(CACHES=DUMMY_CACHE)
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
            session_id="cs_test_54321",
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


@override_settings(CACHES=DUMMY_CACHE)
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
            session_id="cs_test_54321",
        )
        self.book_admin = sample_book(title="Admin")
        self.borrowing_admin = sample_borrowing(
            self.admin, book=self.book_admin
        )
        self.payment_admin = sample_payment(
            self.borrowing_admin,
            session_url="http://1.1.1.1/",
            session_id="cs_test_54321_admin",
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
