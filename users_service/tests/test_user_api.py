from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

USER_CREATE_URL = reverse("users_service:create")
USER_MANAGE_URL = reverse("users_service:manage")


class UserApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_create(self):
        payload = {
            "email": "user@user.com",
            "password": "Password12345",
            "is_staff": True,
        }

        result = self.client.post(USER_CREATE_URL, payload)

        user = get_user_model().objects.get(id=result.data["id"])

        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", result.data)
        self.assertTrue(user.check_password("Password12345"))
        self.assertFalse(user.is_staff)

    def test_user_update_password(self):
        payload = {
            "email": "user@user.com",
            "password": "Password12345",
        }

        new_user = self.client.post(USER_CREATE_URL, payload)

        user = get_user_model().objects.get(id=new_user.data["id"])
        self.client.force_authenticate(user)

        result = self.client.patch(USER_MANAGE_URL, {"password": "Superpass"})
        user.refresh_from_db()

        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(user.check_password("Superpass"))
        self.assertFalse(user.check_password("Password12345"))

    def test_anon_cannot_get_user_manager(self):
        result = self.client.get(USER_MANAGE_URL)

        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)
