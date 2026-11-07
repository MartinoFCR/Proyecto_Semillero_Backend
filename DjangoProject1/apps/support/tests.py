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

    def test_system_error_log_admin_only_and_auto_logging(self):
        from DjangoProject1.apps.support.error_logging import log_system_error
        from DjangoProject1.apps.support.models import SystemErrorLog

        # Cliente normal NO puede ver errores del sistema
        resp_client = self.client.get("/api/support/errors/")
        self.assertEqual(resp_client.status_code, 200)
        self.assertEqual(resp_client.data["count"], 0)

        # Generar error de prueba
        log_entry = log_system_error(
            service="factus",
            level="error",
            endpoint="/v2/bills/validate",
            reference_id="Venta #99",
            error_message="Documento de cliente no valido",
            error_details={"customer.identification": "Invalido"},
            status_code=422,
        )
        self.assertIsNotNone(log_entry)

        # Autenticar como Admin
        user_model = get_user_model()
        admin_user = user_model.objects.create_user(
            username="support-admin",
            password="SecurePassword123!",
            email="admin@example.com",
            identification_number="910000002",
            role=user_model.Role.ADMIN,
        )
        self.client.force_authenticate(admin_user)

        # Admin consulta el listado de errores
        resp_admin = self.client.get("/api/support/errors/?service=factus")
        self.assertEqual(resp_admin.status_code, 200)
        self.assertEqual(resp_admin.data["count"], 1)
        item = resp_admin.data["results"][0]
        self.assertEqual(item["reference_id"], "Venta #99")
        self.assertEqual(item["status_code"], 422)
        self.assertFalse(item["is_resolved"])

        # Admin marca el error como resuelto
        resp_patch = self.client.patch(f"/api/support/errors/{item['id']}/", {"is_resolved": True})
        self.assertEqual(resp_patch.status_code, 200)
        self.assertTrue(resp_patch.data["is_resolved"])

