from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication


class IdentifierTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get("username", "").strip()
        User = get_user_model()
        user = User.objects.filter(email__iexact=identifier).first()
        if user is None:
            user = User.objects.filter(
                identification_number__iexact=identifier
            ).first()
        if user is not None:
            attrs["username"] = user.username
        return super().validate(attrs)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["password_changed_at"] = user.password_changed_at.timestamp()
        token["password_change_required"] = user.password_change_required
        return token


class PasswordVersionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_version = validated_token.get("password_changed_at")
        issued_at = validated_token.get("iat", 0)
        if token_version is not None:
            issued_at = float(token_version)
        if issued_at < user.password_changed_at.timestamp():
            from rest_framework_simplejwt.exceptions import AuthenticationFailed
            raise AuthenticationFailed("La sesión expiró. Inicia sesión nuevamente.")
        return user
