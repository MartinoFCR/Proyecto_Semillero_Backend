import hashlib
import secrets
import uuid
from io import BytesIO
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from smtplib import SMTPException
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from DjangoProject1.apps.accounts.models import AccountActionToken, User
from DjangoProject1.apps.accounts.serializers import (
    CustomerSerializer,
    ProfileSerializer,
    PublicRegistrationSerializer,
    UserSerializer,
)
from DjangoProject1.permissions import IsAdminRole


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save()


class CustomerSearchView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        identification_number = request.query_params.get(
            "identification_number",
            "",
        ).strip()
        if not identification_number:
            return Response(
                {"identification_number": "Este parámetro es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = User.objects.filter(
            role=User.Role.CLIENT,
            identification_number__iexact=identification_number,
        ).first()
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CustomerSerializer(customer).data)


class CustomerListCreateView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        customers = User.objects.filter(
            role=User.Role.CLIENT
        ).order_by("id")
        return Response(CustomerSerializer(customers, many=True).data)

    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return Response(
            CustomerSerializer(customer).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get_object(self, pk):
        return User.objects.filter(
            pk=pk,
            role=User.Role.CLIENT,
        ).first()

    def get(self, request, pk):
        customer = self.get_object(pk)
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CustomerSerializer(customer).data)

    def patch(self, request, pk):
        customer = self.get_object(pk)
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CustomerSerializer(
            customer,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(CustomerSerializer(serializer.save()).data)


class PublicRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PublicRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            ProfileSerializer(serializer.save()).data,
            status=status.HTTP_201_CREATED,
        )


GENERIC_RESET_DETAIL = "Si existe una cuenta asociada, recibirás las instrucciones."
GENERIC_ACTIVATION_DETAIL = "Si corresponde habilitar esta cuenta, recibirás las instrucciones."


def _action_token(user, purpose, request):
    raw_token = secrets.token_urlsafe(32)
    AccountActionToken.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())
    AccountActionToken.objects.create(
        user=user,
        purpose=purpose,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_MINUTES,
        ),
        request_ip=request.META.get("REMOTE_ADDR"),
    )
    return raw_token


def _send_action_email(user, purpose, raw_token):
    if purpose == AccountActionToken.Purpose.PASSWORD_RESET:
        path = "/clientes/restablecer-contrasena#token="
        subject = "Restablece tu contraseña"
    else:
        path = "/clientes/activar-cuenta#token="
        subject = "Activa tu cuenta"
    send_mail(
        subject,
        f"Abre este enlace para continuar: {settings.FRONTEND_BASE_URL}{path}{raw_token}",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def _rate_limited(request, scope, identifier=""):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    keys = [f"account-action:{scope}:ip:{ip}"]
    if identifier:
        keys.append(f"account-action:{scope}:account:{identifier}")
    accepted = [cache.add(key, True, timeout=60) for key in keys]
    return not all(accepted)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if _rate_limited(request, "reset", email):
            return Response(
                {"code": "rate_limited", "detail": "Intenta nuevamente más tarde."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_active:
            raw_token = _action_token(
                user,
                AccountActionToken.Purpose.PASSWORD_RESET,
                request,
            )
            try:
                _send_action_email(user, AccountActionToken.Purpose.PASSWORD_RESET, raw_token)
            except (SMTPException, OSError):
                return Response(
                    {"detail": GENERIC_RESET_DETAIL},
                    status=status.HTTP_202_ACCEPTED,
                )
        return Response({"detail": GENERIC_RESET_DETAIL}, status=status.HTTP_202_ACCEPTED)


class AccountActivationRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if _rate_limited(request, "activation", email):
            return Response(
                {"code": "rate_limited", "detail": "Intenta nuevamente más tarde."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        user = User.objects.filter(
            email__iexact=email,
            role=User.Role.CLIENT,
            is_active=False,
        ).first()
        if user:
            raw_token = _action_token(
                user,
                AccountActionToken.Purpose.ACTIVATION,
                request,
            )
            try:
                _send_action_email(user, AccountActionToken.Purpose.ACTIVATION, raw_token)
            except (SMTPException, OSError):
                return Response(
                    {"detail": GENERIC_ACTIVATION_DETAIL},
                    status=status.HTTP_202_ACCEPTED,
                )
        return Response({"detail": GENERIC_ACTIVATION_DETAIL}, status=status.HTTP_202_ACCEPTED)


class AccountActionConfirmView(APIView):
    permission_classes = [AllowAny]
    purpose = None

    def post(self, request):
        purpose = self.purpose
        raw_token = str(request.data.get("token", ""))
        new_password = request.data.get("new_password")
        if not raw_token or not isinstance(new_password, str):
            return Response(
                {"code": "invalid_or_expired_token", "detail": "El enlace no es válido o ha vencido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with transaction.atomic():
            action = AccountActionToken.objects.select_for_update().filter(
                token_hash=token_hash,
                purpose=purpose,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).select_related("user").first()
            if not action:
                return Response(
                    {"code": "invalid_or_expired_token", "detail": "El enlace no es válido o ha vencido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = action.user
            try:
                password_validation.validate_password(new_password, user)
            except DjangoValidationError as exc:
                return Response(
                    {"new_password": list(exc.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(new_password)
            user.password_changed_at = timezone.now()
            user.password_change_required = False
            if purpose == AccountActionToken.Purpose.ACTIVATION:
                user.is_active = True
            user.save(update_fields=[
                "password",
                "password_changed_at",
                "password_change_required",
                "is_active",
            ])
            revoke_user_refresh_tokens(user)
            action.used_at = timezone.now()
            action.save(update_fields=["used_at"])
            AccountActionToken.objects.filter(
                user=user,
                used_at__isnull=True,
            ).exclude(pk=action.pk).update(used_at=timezone.now())
        detail = (
            "Tu acceso está habilitado. Ya puedes iniciar sesión."
            if purpose == AccountActionToken.Purpose.ACTIVATION
            else "Contraseña actualizada. Inicia sesión nuevamente."
        )
        return Response({"detail": detail})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get("current_password", "")):
            return Response(
                {"current_password": ["La contraseña actual es incorrecta."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_password = request.data.get("new_password")
        try:
            password_validation.validate_password(new_password, user)
        except DjangoValidationError as exc:
            return Response(
                {"new_password": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.password_change_required = False
        user.save(update_fields=[
            "password",
            "password_changed_at",
            "password_change_required",
        ])
        revoke_user_refresh_tokens(user)
        return Response({
            "detail": "Contraseña actualizada. Inicia sesión nuevamente.",
            "reauthentication_required": True,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_refresh = request.data.get("refresh")
        if not raw_refresh:
            return Response(
                {"refresh": ["Este campo es obligatorio."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(raw_refresh)
            if str(refresh.get("user_id")) != str(request.user.pk):
                raise TokenError("El refresh token no pertenece al usuario.")
            refresh.blacklist()
        except TokenError:
            return Response(
                {"code": "invalid_refresh_token", "detail": "El refresh token no es válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


def revoke_user_refresh_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            ProfileSerializer(
                request.user,
                context={"request": request},
            ).data
        )

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(
            ProfileSerializer(
                serializer.save(),
                context={"request": request},
            ).data
        )


class ProfilePhotoView(APIView):
    permission_classes = [IsAuthenticated]
    max_size = 5 * 1024 * 1024
    max_dimension = 2000

    def post(self, request):
        photo = request.FILES.get("photo")
        if not photo:
            return Response(
                {"photo": "El archivo photo es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if photo.size > self.max_size:
            return Response(
                {"photo": "La imagen no puede superar 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            photo.seek(0)
            image = Image.open(photo)
            image_format = image.format
            width, height = image.size
            image.verify()
            photo.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            return Response(
                {"photo": "El archivo no es una imagen válida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_format not in {"JPEG", "PNG", "WEBP"}:
            return Response(
                {"photo": "Solo se admiten JPG, PNG y WEBP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if width > self.max_dimension or height > self.max_dimension:
            return Response(
                {"photo": "Las dimensiones máximas son 2000 x 2000 píxeles."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        photo.seek(0)
        image = Image.open(photo)
        output = BytesIO()
        extension = {
            "JPEG": ("jpg", "JPEG"),
            "PNG": ("png", "PNG"),
            "WEBP": ("webp", "WEBP"),
        }[image_format]
        if image_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(output, format=extension[1], optimize=True)
        output.seek(0)
        old_photo_name = request.user.photo.name if request.user.photo else None
        request.user.photo.save(
            f"{uuid.uuid4().hex}.{extension[0]}",
            ContentFile(output.read()),
            save=False,
        )
        request.user.save(update_fields=["photo"])
        if old_photo_name:
            request.user.photo.storage.delete(old_photo_name)
        return Response(
            ProfileSerializer(
                request.user,
                context={"request": request},
            ).data
        )

    def delete(self, request):
        if request.user.photo:
            photo = request.user.photo
            request.user.photo = None
            request.user.save(update_fields=["photo"])
            photo.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DigitalCardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = signing.Signer(salt="client-card").sign(
            str(request.user.card_id)
        )
        verification_url = request.build_absolute_uri(
            reverse("card-verify"),
        )
        return Response({
            "name": (
                f"{request.user.first_name} {request.user.last_name}"
            ).strip(),
            "card_id": str(request.user.card_id),
            "photo_url": ProfileSerializer(
                request.user,
                context={"request": request},
            ).data["photo_url"],
            "status": "active" if request.user.is_active else "revoked",
            "valid_until": None,
            "validity": "indefinite_while_active",
            "qr": {
                "token": token,
                "verification_url": verification_url,
            },
            "warning": "Este carné no sustituye un tiquete ni acredita una compra.",
        })


class CardVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "")
        try:
            card_id = signing.Signer(salt="client-card").unsign(token)
            user = User.objects.get(card_id=card_id)
        except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
            return Response(
                {"valid": False, "detail": "El carné no es válido."},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = Response({
            "valid": user.is_active,
            "card_id": str(user.card_id),
            "name": user.first_name,
            "status": "active" if user.is_active else "revoked",
            "valid_until": None,
            "validity": "indefinite_while_active",
        })
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response
