from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from books_service.models import Book
from books_service.serializers import BookSerializer, BookListSerializer


DUMMY_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache"
    }
}


BOOK_URL = reverse("books_service:book-list")


def detail_url(book_id):
    return reverse("books_service:book-detail", args=[book_id])


def sample_book(**params):
    defaults = {
        "title": "Harry Potter and the Philosopher's Stone",
        "author": "Joanne Rowling",
        "cover": Book.Cover.HARD,
        "inventory": 5,
        "daily_fee": Decimal("1.49")
    }
    defaults.update(params)

    return Book.objects.create(**defaults)


@override_settings(CACHES=DUMMY_CACHE)
class UnauthenticatedBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.book = sample_book()
        self.book_not_available = sample_book(
            title="Harry Potter and the Chamber of Secrets",
            inventory=0
        )

    def test_get_book_list(self):
        result = self.client.get(BOOK_URL)

        books = Book.objects.all()
        serializer = BookListSerializer(books, many=True)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data, serializer.data)
        self.assertEqual(len(result.data), len(serializer.data))
        self.assertIn("is_available", result.data[0])
        self.assertIn("daily_fee", result.data[0])
        self.assertNotIn("inventory", result.data[0])
        self.assertTrue(self.book.is_available)
        self.assertFalse(self.book_not_available.is_available)

    def test_retrieve_book_detail(self):
        url = detail_url(self.book.id)
        result = self.client.get(url)

        serializer = BookSerializer(self.book)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data, serializer.data)

    def test_create_book_unauthorized(self):
        payload = {
            "title": "Harry Potter and the Chamber of Secrets",
            "author": "Joanne Rowling",
            "cover": Book.Cover.HARD,
            "inventory": 5,
            "daily_fee": Decimal("1.49")
        }

        result = self.client.post(BOOK_URL, payload)

        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CACHES=DUMMY_CACHE)
class AuthenticatedBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@user.com",
            password="password",
        )
        self.client.force_authenticate(self.user)

    def test_create_book_forbidden(self):
        payload = {
            "title": "Harry Potter and the Chamber of Secrets",
            "author": "Joanne Rowling",
            "cover": Book.Cover.HARD,
            "inventory": 5,
            "daily_fee": Decimal("1.49")
        }

        result = self.client.post(BOOK_URL, payload)

        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(CACHES=DUMMY_CACHE)
class AdminBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="admin@admin.com",
            password="password",
            is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.book = sample_book()

    def test_create_book(self):
        payload = {
            "title": "Harry Potter and the Chamber of Secrets",
            "author": "Joanne Rowling",
            "cover": Book.Cover.SOFT,
            "inventory": 5,
            "daily_fee": Decimal("1.49")
        }

        result = self.client.post(BOOK_URL, payload)

        book = Book.objects.get(id=result.data["id"])

        self.assertEqual(result.status_code, status.HTTP_201_CREATED)

        for key in payload:
            self.assertEqual(payload[key], getattr(book, key))

    def test_patch_book(self):
        url = detail_url(self.book.id)

        result = self.client.patch(url, {"author": "Santori"})

        book = Book.objects.get(id=self.book.id)

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data["author"], book.author)
        self.assertEqual("Santori", book.author)

    def test_delete_book(self):
        url = detail_url(self.book.id)

        result = self.client.delete(url)

        self.assertEqual(
            result.status_code,
            status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(
            Book.objects.filter(id=self.book.id).exists()
        )

    def test_create_book_with_negative_inventory_not_allowed(self):
        payload = {
            "title": "Harry Potter and the Chamber of Secrets",
            "author": "Joanne Rowling",
            "cover": Book.Cover.SOFT,
            "inventory": -5,
            "daily_fee": Decimal("1.49")
        }

        result = self.client.post(BOOK_URL, payload)

        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("inventory", result.data)
