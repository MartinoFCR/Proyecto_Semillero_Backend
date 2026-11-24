from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .serializers import AdminUserSerializer, CustomerSerializer
from .models import LoginAttempt


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
        self.user.set_password("testpass123")
        self.user.is_active = True
        self.user.save(update_fields=["password", "is_active"])
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

    def test_password_change_required_is_enforced_by_api(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="temporary-customer",
            password="900000004",
            email="temporary@example.com",
            identification_number="900000004",
            role=user_model.Role.CLIENT,
            password_change_required=True,
        )
        self.client.force_authenticate(user=None)
        login = self.client.post(
            "/api/token/",
            {"username": customer.email, "password": "900000004"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
        )
        blocked = self.client.get("/api/sales/sales/")
        self.assertEqual(blocked.status_code, 401)
        allowed = self.client.get("/api/accounts/me/")
        self.assertEqual(allowed.status_code, 200)

    def test_logout_revokes_refresh_token(self):
        LoginAttempt.objects.all().delete()
        login = self.client.post(
            "/api/token/",
            {"username": self.user.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
        )
        logout = self.client.post(
            "/api/accounts/logout/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, 204)
        refresh = self.client.post(
            "/api/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, 401)

    def test_login_throttle_uses_shared_database_records(self):
        LoginAttempt.objects.all().delete()
        for _ in range(5):
            response = self.client.post(
                "/api/token/",
                {"username": self.user.email, "password": "wrong-password"},
                format="json",
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            "/api/token/",
            {"username": self.user.email, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 429)

    def test_only_admins_can_manage_admin_users(self):
        user_model = get_user_model()
        # Un cliente autenticado no puede listar ni crear administradores (403 Forbidden)
        forbidden_list = self.client.get("/api/accounts/admins/")
        self.assertEqual(forbidden_list.status_code, 403)
        forbidden_create = self.client.post(
            "/api/accounts/admins/",
            {
                "identification_number": "800000001",
                "name": "Nuevo Admin",
                "email": "nuevo.admin@example.com",
            },
            format="json",
        )
        self.assertEqual(forbidden_create.status_code, 403)

        # Autenticado como administrador existente
        existing_admin = user_model.objects.create_user(
            username="root_admin",
            password="AdminPassword123!",
            email="root.admin@example.com",
            identification_number="800000000",
            first_name="Root",
            last_name="Admin",
            role=user_model.Role.ADMIN,
        )
        self.client.force_authenticate(existing_admin)

        # Crear nuevo administrador con contraseña explícita
        create_resp = self.client.post(
            "/api/accounts/admins/",
            {
                "identification_document_code": "13",
                "identification_number": "800000002",
                "first_name": "Carlos",
                "last_name": "Gomez",
                "email": "carlos.admin@example.com",
                "telephone": "3150001122",
                "password": "CarlosSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        self.assertEqual(create_resp.data["role"], "admin")
        self.assertEqual(create_resp.data["name"], "Carlos Gomez")
        self.assertFalse(create_resp.data["password_change_required"])

        created_admin = user_model.objects.get(pk=create_resp.data["id"])
        self.assertEqual(created_admin.role, user_model.Role.ADMIN)
        self.assertTrue(created_admin.is_staff)
        self.assertTrue(created_admin.check_password("CarlosSecurePass123!"))

        # Crear administrador sin contraseña (usa documento como clave inicial)
        create_default_pw = self.client.post(
            "/api/accounts/admins/",
            {
                "identification_number": "800000003",
                "name": "Laura Martinez",
                "email": "laura.admin@example.com",
            },
            format="json",
        )
        self.assertEqual(create_default_pw.status_code, 201, create_default_pw.data)
        self.assertTrue(create_default_pw.data["password_change_required"])
        laura = user_model.objects.get(pk=create_default_pw.data["id"])
        self.assertTrue(laura.check_password("800000003"))

        # No puede eliminarse a sí mismo
        self_delete = self.client.delete(f"/api/accounts/admins/{existing_admin.id}/")
        self.assertEqual(self_delete.status_code, 400)
