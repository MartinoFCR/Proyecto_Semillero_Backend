from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .serializers import CustomerSerializer


class ClientProfileTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="client",
            password="secret-pass-123",
            email="client@example.com",
            identification_number="900000001",
            first_name="Client",
            role=get_user_model().Role.CLIENT,
        )
        self.client.force_authenticate(self.user)

    def test_profile_photo_and_card_verification(self):
        image_buffer = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(image_buffer, format="PNG")
        image = SimpleUploadedFile(
            "profile.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )

        photo_response = self.client.post(
            "/api/accounts/me/photo/",
            {"photo": image},
            format="multipart",
        )
        self.assertEqual(photo_response.status_code, 200)
        self.assertIsNotNone(photo_response.data["photo_url"])

        card_response = self.client.get("/api/accounts/me/card/")
        self.assertEqual(card_response.status_code, 200)
        token = card_response.data["qr"]["token"]
        verification = self.client.get(
            "/api/accounts/cards/verify/",
            {"token": token},
        )
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.data["valid"])

        delete_response = self.client.delete("/api/accounts/me/photo/")
        self.assertEqual(delete_response.status_code, 204)

    def test_profile_webp_url_is_served_with_image_content_type(self):
        image_buffer = BytesIO()
        Image.new("RGB", (20, 20), "green").save(image_buffer, format="WEBP")
        image = SimpleUploadedFile(
            "profile.webp",
            image_buffer.getvalue(),
            content_type="image/webp",
        )

        upload_response = self.client.post(
            "/api/accounts/me/photo/",
            {"photo": image},
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 200)
        photo_url = upload_response.data["photo_url"]
        photo_response = self.client.get(photo_url)
        self.assertEqual(photo_response.status_code, 200)
        self.assertEqual(photo_response["Content-Type"], "image/webp")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_is_single_use(self):
        cache.clear()
        response = self.client.post(
            "/api/accounts/password/reset/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        token = mail.outbox[0].body.rsplit("#token=", 1)[1]
        confirm = self.client.post(
            "/api/accounts/password/reset/confirm/",
            {"token": token, "new_password": "NewSecurePassword123!"},
            format="json",
        )
        self.assertEqual(confirm.status_code, 200)
        reused = self.client.post(
            "/api/accounts/password/reset/confirm/",
            {"token": token, "new_password": "AnotherSecurePassword123!"},
            format="json",
        )
        self.assertEqual(reused.status_code, 400)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_created_account_activation(self):
        user_model = get_user_model()
        inactive = user_model.objects.create(
            username="customer_900000002",
            email="inactive@example.com",
            identification_number="900000002",
            role=user_model.Role.CLIENT,
            is_active=False,
        )
        inactive.set_unusable_password()
        inactive.save()
        cache.clear()
        response = self.client.post(
            "/api/accounts/activation/request/",
            {"email": inactive.email},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        token = mail.outbox[-1].body.rsplit("#token=", 1)[1]
        confirm = self.client.post(
            "/api/accounts/activation/confirm/",
            {"token": token, "new_password": "NewSecurePassword123!"},
            format="json",
        )
        self.assertEqual(confirm.status_code, 200)
        inactive.refresh_from_db()
        self.assertTrue(inactive.is_active)
        self.assertTrue(inactive.check_password("NewSecurePassword123!"))

    def test_admin_created_customer_uses_document_as_initial_password(self):
        user_model = get_user_model()
        serializer = CustomerSerializer(data={
            "identification_document_code": "13",
            "identification_number": "900000003",
            "name": "Admin Created",
            "email": "admin-created@example.com",
            "telephone": "3001234567",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        customer = serializer.save()
        self.assertTrue(customer.is_active)
        self.assertTrue(customer.check_password("900000003"))
        self.assertTrue(customer.password_change_required)
