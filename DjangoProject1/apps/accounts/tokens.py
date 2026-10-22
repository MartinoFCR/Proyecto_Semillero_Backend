from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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
