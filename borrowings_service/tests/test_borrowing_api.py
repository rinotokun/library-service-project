from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, ANY

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework import status
import stripe

from books_service.models import Book

from borrowings_service.models import Borrowing
from borrowings_service.serializers import (
    BorrowingListSerializer,
    BorrowingDetailSerializer,
)

from payments_service.models import Payment
from users_service.serializers import UserShortInfoSerializer

BORROWING_URL = reverse("borrowings_service:borrowing-list")


def borrowing_return_url(borrowing_id):
    return reverse(
        "borrowings_service:borrowing-return-book", args=[borrowing_id]
    )


def borrowing_detail_url(borrowing_id):
    return reverse("borrowings_service:borrowing-detail", args=[borrowing_id])


def book_detail_url(book_id):
    return reverse("books_service:book-detail", args=[book_id])


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


class UnauthenticatedBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.book = sample_book()

    def test_auth_required_for_borrowing_list(self):
        result = self.client.get(BORROWING_URL)

        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_required_for_create_borrowing(self):
        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": self.book.id,
        }
        result = self.client.post(BORROWING_URL, payload)

        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedBorrowingApiTests(TestCase):
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
        self.book_two = sample_book(title="Two")
        self.borrowing_user1 = sample_borrowing(self.user1, book=self.book_one)
        self.borrowing_user2 = sample_borrowing(self.user2, book=self.book_two)

    def test_see_only_own_borrowings(self):
        result = self.client.get(BORROWING_URL)

        for borrowing in result.data:
            self.assertTrue(borrowing["is_active"])
            del borrowing["is_active"]

        borrowing_user1 = Borrowing.objects.filter(user=self.user1)
        serializer_user1 = BorrowingListSerializer(borrowing_user1, many=True)

        user_short_info = UserShortInfoSerializer(self.user1, many=False)

        borrowing_user2 = Borrowing.objects.filter(user=self.user2)
        serializer_user2 = BorrowingListSerializer(borrowing_user2, many=True)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data, serializer_user1.data)
        self.assertNotEqual(result.data, serializer_user2.data)
        self.assertEqual(result.data[0]["book"], self.book_one.title)
        self.assertEqual(result.data[0]["user"], user_short_info.data)

    def test_retrieve_borrowing_detail(self):
        url = borrowing_detail_url(self.borrowing_user1.id)
        result = self.client.get(url)

        borrowing_user1_detail = BorrowingDetailSerializer(
            self.borrowing_user1, many=False
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data, borrowing_user1_detail.data)

    def test_cannot_get_not_own_borrowing_detail(self):
        url = borrowing_detail_url(self.borrowing_user2.id)
        result = self.client.get(url)

        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    @patch("borrowings_service.views.create_checkout_session")
    @patch("borrowings_service.views.notify_admin_via_telegram")
    def test_borrowing_book_if_available(
        self, mock_notify_via_telegram, mock_create_checkout_session
    ):
        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": self.book_one.id,
        }
        book_one_inventory_before_borrowing = self.book_one.inventory

        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.post(BORROWING_URL, payload)

        self.book_one.refresh_from_db()
        book_one_inventory_after_borrowing = self.book_one.inventory

        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            book_one_inventory_before_borrowing - 1,
            book_one_inventory_after_borrowing,
        )
        self.assertEqual(result.data["user"], self.user1.id)
        self.assertEqual(
            result.data["borrow_date"],
            timezone.localdate().strftime("%Y-%m-%d"),
        )

        mock_notify_via_telegram.delay.assert_called_once()
        message = mock_notify_via_telegram.delay.call_args.args[0]
        self.assertIn(timezone.localdate().strftime("%Y-%m-%d"), message)
        self.assertIn(
            payload["expected_return_date"].strftime("%Y-%m-%d"), message
        )
        self.assertIn(self.user1.email, message)
        self.assertIn(self.book_one.title, message)

        borrowing = Borrowing.objects.get(id=result.data["id"])
        mock_create_checkout_session.assert_called_once_with(borrowing, ANY)

    @patch("borrowings_service.views.create_checkout_session")
    @patch("borrowings_service.views.notify_admin_via_telegram")
    def test_borrowing_book_with_zero_inventory(
        self, mock_notify_via_telegram, mock_create_checkout_session
    ):
        book = sample_book(title="Three", inventory=0)
        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": book.id,
        }
        borrowings_before_post_method = Borrowing.objects.count()

        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.post(BORROWING_URL, payload)
        book.refresh_from_db()
        borrowings_after_post_method = Borrowing.objects.count()

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book", result.data)
        self.assertEqual(book.inventory, 0)
        self.assertEqual(
            borrowings_before_post_method, borrowings_after_post_method
        )
        mock_notify_via_telegram.delay.assert_not_called()

    @patch("borrowings_service.services.stripe.checkout.Session.create")
    @patch("borrowings_service.views.notify_admin_via_telegram")
    def test_borrowing_returns_503_if_stripe_fails(
        self, mock_notify_via_telegram, mock_stripe_checkout_session_create
    ):
        mock_stripe_checkout_session_create.side_effect = stripe.StripeError

        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": self.book_one.id,
        }
        book_one_inventory_before_borrowing = self.book_one.inventory
        borrowing_before_post = Borrowing.objects.count()

        result = self.client.post(BORROWING_URL, payload)

        self.book_one.refresh_from_db()
        book_one_inventory_after_borrowing = self.book_one.inventory
        borrowing_after_post = Borrowing.objects.count()
        payments = Payment.objects.count()

        self.assertEqual(
            result.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(
            book_one_inventory_before_borrowing,
            book_one_inventory_after_borrowing,
        )
        self.assertEqual(borrowing_before_post, borrowing_after_post)
        self.assertEqual(payments, 0)
        mock_notify_via_telegram.delay.assert_not_called()

    def test_should_return_400_when_expected_return_date_is_today(self):
        payload = {
            "expected_return_date": timezone.localdate(),
            "book": self.book_one.id,
        }
        borrowings_before_post_method = Borrowing.objects.count()
        book_one_inventory_before_borrowing = self.book_one.inventory

        result = self.client.post(BORROWING_URL, payload)
        self.book_one.refresh_from_db()
        borrowings_after_post_method = Borrowing.objects.count()
        book_one_inventory_after_borrowing = self.book_one.inventory

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expected_return_date", result.data)
        self.assertEqual(
            borrowings_before_post_method, borrowings_after_post_method
        )
        self.assertEqual(
            book_one_inventory_before_borrowing,
            book_one_inventory_after_borrowing,
        )

    def test_should_return_400_when_expected_return_date_is_yesterday(self):
        payload = {
            "expected_return_date": timezone.localdate() - timedelta(days=1),
            "book": self.book_one.id,
        }
        borrowings_before_post_method = Borrowing.objects.count()
        book_one_inventory_before_borrowing = self.book_one.inventory

        result = self.client.post(BORROWING_URL, payload)
        self.book_one.refresh_from_db()
        borrowings_after_post_method = Borrowing.objects.count()
        book_one_inventory_after_borrowing = self.book_one.inventory

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expected_return_date", result.data)
        self.assertEqual(
            borrowings_before_post_method, borrowings_after_post_method
        )
        self.assertEqual(
            book_one_inventory_before_borrowing,
            book_one_inventory_after_borrowing,
        )

    @patch("borrowings_service.views.create_checkout_session")
    @patch("borrowings_service.views.notify_admin_via_telegram")
    def test_ignore_borrow_date_and_user(
        self, mock_notify_via_telegram, mock_create_checkout_session
    ):
        borrow_date = timezone.localdate() - timedelta(days=1)
        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": self.book_one.id,
            "borrow_date": borrow_date,
            "user": self.user2,
        }

        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.post(BORROWING_URL, payload)

        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            result.data["borrow_date"],
            timezone.localdate().strftime("%Y-%m-%d"),
        )
        self.assertEqual(result.data["user"], self.user1.id)

        mock_notify_via_telegram.delay.assert_called_once()
        message = mock_notify_via_telegram.delay.call_args.args[0]
        self.assertNotIn(borrow_date.strftime("%Y-%m-%d"), message)
        self.assertNotIn(self.user2.email, message)

    @patch("borrowings_service.views.create_checkout_session")
    @patch("borrowings_service.views.notify_admin_via_telegram")
    def test_borrow_return_endpoint(
        self, mock_notify_via_telegram, mock_create_checkout_session
    ):
        payload = {
            "expected_return_date": timezone.localdate() + timedelta(days=1),
            "book": self.book_one.id,
        }

        with self.captureOnCommitCallbacks(execute=True):
            borrowing_result = self.client.post(BORROWING_URL, payload)

        self.book_one.refresh_from_db()
        mock_notify_via_telegram.delay.assert_called_once()

        book_one_inventory_before_return = self.book_one.inventory
        url = borrowing_return_url(borrowing_result.data["id"])

        result = self.client.post(url)
        self.book_one.refresh_from_db()
        book_one_inventory_after_return = self.book_one.inventory

        borrowings = self.client.get(BORROWING_URL)
        borrowings_ids = [borrowing["id"] for borrowing in borrowings.data]
        self.assertIn(borrowing_result.data["id"], borrowings_ids)

        for borrowing in borrowings.data:
            if borrowing["id"] == borrowing_result.data["id"]:
                self.assertFalse(borrowing["is_active"])

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(
            result.data["actual_return_date"],
            timezone.localdate().strftime("%Y-%m-%d"),
        )
        self.assertEqual(
            book_one_inventory_before_return + 1,
            book_one_inventory_after_return,
        )
        mock_create_checkout_session.assert_called_once()

    def test_cannot_return_twice_same_borrowing(self):
        url = borrowing_return_url(self.borrowing_user1.id)

        self.client.post(url)
        self.book_one.refresh_from_db()
        book_one_inventory_after_first_return = self.book_one.inventory

        invalid_return = self.client.post(url)
        self.book_one.refresh_from_db()
        book_one_inventory_after_invalid_return = self.book_one.inventory

        self.assertEqual(
            invalid_return.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            book_one_inventory_after_first_return,
            book_one_inventory_after_invalid_return,
        )

    def test_cannot_return_not_own_borrowing(self):
        url = borrowing_return_url(self.borrowing_user2.id)
        book_two_inventory_before_return = self.book_two.inventory

        result = self.client.post(url)
        self.book_two.refresh_from_db()
        book_two_inventory_after_return = self.book_two.inventory

        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            book_two_inventory_before_return, book_two_inventory_after_return
        )

    @patch("borrowings_service.views.create_checkout_session")
    def test_return_borrowing_in_expected_return_date(
        self, mock_create_checkout_session
    ):
        borrowing = sample_borrowing(
            self.user1,
            book=self.book_two,
            borrow_date=timezone.localdate() - timedelta(days=1),
            expected_return_date=timezone.localdate(),
        )
        url = borrowing_return_url(borrowing.id)

        result = self.client.post(url)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        mock_create_checkout_session.assert_not_called()

    @patch("borrowings_service.views.create_checkout_session")
    def test_return_overdue_borrowing(self, mock_create_checkout_session):
        borrowing = sample_borrowing(
            self.user1,
            book=self.book_two,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() - timedelta(days=3),
        )
        url = borrowing_return_url(borrowing.id)

        result = self.client.post(url)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(True, mock_create_checkout_session.call_args.args[2])
        mock_create_checkout_session.assert_called_once()

    @patch("borrowings_service.views.create_checkout_session")
    def test_return_borrowing_when_stripe_unavailable(
        self, mock_create_checkout_session
    ):
        mock_create_checkout_session.side_effect = stripe.StripeError
        borrowing = sample_borrowing(
            self.user1,
            book=self.book_two,
            borrow_date=timezone.localdate() - timedelta(days=5),
            expected_return_date=timezone.localdate() - timedelta(days=3),
        )
        url = borrowing_return_url(borrowing.id)
        book_two_inventory_before_return = self.book_two.inventory

        result = self.client.post(url)

        self.book_two.refresh_from_db()
        borrowing.refresh_from_db()
        book_two_inventory_after_return = self.book_two.inventory

        self.assertEqual(
            result.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(
            book_two_inventory_before_return,
            book_two_inventory_after_return,
        )
        self.assertIsNone(borrowing.actual_return_date)


class AdminBorrowingApiTests(TestCase):
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
        self.book_two = sample_book(title="Two")
        self.book_three = sample_book(title="Three")

        self.borrowing_admin = sample_borrowing(self.admin, book=self.book_one)
        self.borrowing_user1 = sample_borrowing(self.user1, book=self.book_two)
        self.borrowing_user2 = sample_borrowing(
            self.user2, book=self.book_three
        )

    def test_admin_see_all_borrowings(self):
        result = self.client.get(BORROWING_URL)
        all_borrowings_in_db = Borrowing.objects.count()

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(len(result.data), all_borrowings_in_db)

    def test_cannot_delete_book_if_borrowed_is_active(self):
        url = book_detail_url(self.book_one.id)

        result = self.client.delete(url)

        self.assertEqual(result.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Book.objects.filter(id=self.book_one.id).exists())

    def test_cannot_delete_book_if_borrowed_is_not_active(self):
        url_for_return_borrowing = borrowing_return_url(
            self.borrowing_admin.id
        )
        result_return_borrowing = self.client.post(url_for_return_borrowing)

        url_for_delete_book = book_detail_url(self.book_one.id)

        result_delete_book = self.client.delete(url_for_delete_book)

        self.assertEqual(
            result_delete_book.status_code, status.HTTP_409_CONFLICT
        )
        self.assertEqual(
            result_return_borrowing.status_code, status.HTTP_200_OK
        )
        self.assertTrue(Book.objects.filter(id=self.book_one.id).exists())


class BorrowingFilterApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@admin.com", password="password", is_staff=True
        )

        self.user1 = get_user_model().objects.create_user(
            email="user1@user.com",
            password="password",
        )
        self.user2 = get_user_model().objects.create_user(
            email="user2@user.com",
            password="password",
        )

        self.book_one = sample_book(title="One")
        self.book_two = sample_book(title="Two")
        self.book_three = sample_book(title="Three")

        self.borrowing_admin = sample_borrowing(self.admin, book=self.book_one)
        self.returned_borrowing_admin = sample_borrowing(
            self.admin,
            book=sample_book(title="Four"),
            actual_return_date=timezone.localdate(),
        )
        self.borrowing_user1 = sample_borrowing(self.user1, book=self.book_two)
        self.returned_borrowing_user1 = sample_borrowing(
            self.user1,
            book=sample_book(title="Five"),
            actual_return_date=timezone.localdate(),
        )
        self.borrowing_user2 = sample_borrowing(
            self.user2, book=self.book_three
        )
        self.returned_borrowing_user2 = sample_borrowing(
            self.user2,
            book=sample_book(title="Six"),
            actual_return_date=timezone.localdate(),
        )

    def test_is_active_true_for_not_staff(self):
        self.client.force_authenticate(self.user1)

        result = self.client.get(BORROWING_URL, {"is_active": "true"})

        borrowings_ids = [borrowing["id"] for borrowing in result.data]

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertIn(self.borrowing_user1.id, borrowings_ids)
        self.assertEqual(len(borrowings_ids), 1)

    def test_is_active_false_for_not_staff(self):
        self.client.force_authenticate(self.user1)

        result = self.client.get(BORROWING_URL, {"is_active": "false"})

        borrowings_ids = [borrowing["id"] for borrowing in result.data]

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertIn(self.returned_borrowing_user1.id, borrowings_ids)
        self.assertEqual(len(borrowings_ids), 1)

    def test_user_id_ignored_if_not_staff(self):
        self.client.force_authenticate(self.user1)

        result = self.client.get(BORROWING_URL, {"user_id": self.admin.id})

        user_ids = [borrowing["user"]["id"] for borrowing in result.data]
        borrowings_user1 = Borrowing.objects.filter(user=self.user1).count()

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1.id, user_ids)
        self.assertNotIn(self.admin.id, user_ids)
        self.assertNotIn(self.user2.id, user_ids)
        self.assertEqual(len(user_ids), borrowings_user1)

    def test_admin_get_by_user_id_returns_only_target_user_data(self):
        self.client.force_authenticate(self.admin)

        result = self.client.get(BORROWING_URL, {"user_id": self.user1.id})

        user_ids = [borrowing["user"]["id"] for borrowing in result.data]
        borrowings_user1 = Borrowing.objects.filter(user=self.user1).count()

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertIn(self.user1.id, user_ids)
        self.assertNotIn(self.admin.id, user_ids)
        self.assertNotIn(self.user2.id, user_ids)
        self.assertEqual(len(user_ids), borrowings_user1)

    def test_filter_by_user_id_and_is_active_combined_success(self):
        self.client.force_authenticate(self.admin)

        result = self.client.get(
            BORROWING_URL, {"user_id": self.user1.id, "is_active": "false"}
        )

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(
            result.data[0]["id"], self.returned_borrowing_user1.id
        )

    def test_is_active_case_insensitivity(self):
        self.client.force_authenticate(self.admin)

        for value in ("False", "false", "FALSE"):
            with self.subTest(is_active=value):
                result = self.client.get(BORROWING_URL, {"is_active": value})

                borrowings = Borrowing.objects.filter(
                    actual_return_date__isnull=False
                )
                serializer = BorrowingListSerializer(borrowings, many=True)

                expected_borrowings = [
                    borrowing["id"] for borrowing in serializer.data
                ]
                actual_borrowings = [
                    borrowing["id"] for borrowing in result.data
                ]

                self.assertEqual(result.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    set(expected_borrowings), set(actual_borrowings)
                )

    def test_is_active_invalid_integer_returns_400_with_field_error(self):
        self.client.force_authenticate(self.admin)

        result = self.client.get(BORROWING_URL, {"is_active": 1})

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_active", result.data)

    def test_user_id_invalid_string_returns_400_with_field_error(self):
        self.client.force_authenticate(self.admin)

        result = self.client.get(BORROWING_URL, {"user_id": "fafa"})

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_id", result.data)
