from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITestCase


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
