from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class SupportRequestTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="support-client",
            password="SecurePassword123!",
            email="support@example.com",
            identification_number="910000001",
            role=user_model.Role.CLIENT,
        )
        self.client.force_authenticate(self.user)

    def test_customer_creates_and_lists_only_own_requests(self):
        response = self.client.post(
            "/api/support/requests/",
            {
                "category": "account",
                "subject": "Ayuda con mi cuenta",
                "message": "Necesito actualizar mis datos.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["reference"], "SOL-000001")
        listing = self.client.get("/api/support/requests/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
