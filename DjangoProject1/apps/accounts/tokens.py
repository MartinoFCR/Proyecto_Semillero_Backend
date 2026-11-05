from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed, Throttled
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import LoginAttempt


class IdentifierTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get("username", "").strip()
        request = self.context.get("request")
        ip = request.META.get("REMOTE_ADDR", "unknown") if request else "unknown"
        keys = [f"ip:{ip}", f"account:{identifier.lower()}"]
        now = timezone.now()
        with transaction.atomic():
            attempts = list(
                LoginAttempt.objects.select_for_update().filter(key__in=keys)
            )
            blocked = any(
                attempt.window_started_at
                + timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS) > now
                and attempt.failures >= settings.LOGIN_FAILURE_LIMIT
                for attempt in attempts
            )
        if blocked:
            raise Throttled(
                detail="Demasiados intentos. Intenta nuevamente más tarde.",
                wait=settings.LOGIN_FAILURE_WINDOW_SECONDS,
            )
        User = get_user_model()
        user = User.objects.filter(email__iexact=identifier).first()
        if user is None:
            user = User.objects.filter(
                identification_number__iexact=identifier
            ).first()
        if user is not None:
            attrs["username"] = user.username
        try:
            result = super().validate(attrs)
        except AuthenticationFailed:
            with transaction.atomic():
                for key in keys:
                    attempt, created = LoginAttempt.objects.select_for_update().get_or_create(
                        key=key,
                        defaults={"window_started_at": now, "failures": 0},
                    )
                    if (
                        attempt.window_started_at
                        + timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS)
                        <= now
                    ):
                        attempt.window_started_at = now
                        attempt.failures = 0
                    attempt.failures += 1
                    attempt.save(update_fields=["window_started_at", "failures"])
            raise
        LoginAttempt.objects.filter(key__in=keys).delete()
        return result

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["password_changed_at"] = user.password_changed_at.timestamp()
        token["password_change_required"] = user.password_change_required
        return token


class PasswordVersionJWTAuthentication(JWTAuthentication):
    allowed_paths = {
        "/api/accounts/me",
        "/api/accounts/me/password",
        "/api/accounts/me/photo",
        "/api/accounts/me/card",
        "/api/accounts/logout",
    }

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if (
            user.role != "admin"
            and user.password_change_required
            and request.path.rstrip("/") not in self.allowed_paths
        ):
            raise AuthenticationFailed({
                "code": "password_change_required",
                "detail": "Debes cambiar tu contraseña antes de continuar.",
            })
        return result

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_version = validated_token.get("password_changed_at")
        issued_at = validated_token.get("iat", 0)
        if token_version is not None:
            issued_at = float(token_version)
        if issued_at < user.password_changed_at.timestamp():
            raise AuthenticationFailed("La sesión expiró. Inicia sesión nuevamente.")
        return user
