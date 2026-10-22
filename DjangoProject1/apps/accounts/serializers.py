from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        trim_whitespace=False
    )
    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )

    role = serializers.ChoiceField(
        choices=User.Role.choices,
        read_only=True
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "telephone",
            "identification_number",
            "role",
            "first_name",
            "last_name",
            "password",
        )
        read_only_fields = ("id", "role")

    def validate_password(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Este campo es obligatorio."})
        return attrs
    
    def validate_username(self, value):
        value = value.strip()
        
        if self.instance is None and not value.get("username"):
            raise serializers.ValidationError({"username": "Este campo es obligatorio."})
        
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Este nombre de usuario ya está registrado."
            )
        return value

    def validate_email(self, value):
        value = value.strip().lower()

        if not value:
            raise serializers.ValidationError(
                "El correo electrónico es obligatorio."
            )

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Este correo electrónico ya está registrado."
            )

        return value

    def validate_identification_number(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El número de identificación es obligatorio."
            )

        if len(value) > 20:
            raise serializers.ValidationError(
                "La identificación no puede superar los 20 caracteres."
            )

        # Política de ejemplo: letras, números, puntos y guiones.
        import re

        if not re.fullmatch(r"[A-Za-z0-9.-]+", value):
            raise serializers.ValidationError(
                "La identificación contiene caracteres no permitidos."
            )

        if User.objects.filter(
            identification_number__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "Este número de identificación ya está registrado."
            )

        return value

    def validate_role(self, value):
        forbidden_roles = {"admin", "driver"}

        if value.lower() in forbidden_roles:
            raise serializers.ValidationError(
                "No puedes registrarte con este rol."
            )

        valid_roles = {choice[0] for choice in User.Role.choices}

        if value not in valid_roles:
            raise serializers.ValidationError(
                "El rol seleccionado no es válido."
            )

        return value

    def validate_first_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El nombre no puede contener únicamente espacios."
            )

        return value

    def validate_last_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El apellido no puede contener únicamente espacios."
            )

        return value

    def validate(self, attrs):
        # Ejecuta los validadores de contraseña configurados en Django.
        candidate_user = User(**{
            key: value
            for key, value in attrs.items()
            if key != "password"
        })

        try:
            password_validation.validate_password(
                attrs["password"],
                user=candidate_user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": list(exc.messages)
            })

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")

        # set_password aplica el hash; nunca guardar la contraseña.
        user = User(**validated_data)
        user.set_password(password)
        user.role = User.Role.CLIENT  # Forzamos el rol a CLIENT para registros públicos.

        # Los privilegios se fijan en el servidor.
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False

        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user


class CustomerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        source="first_name",
        max_length=150,
        allow_blank=False,
    )
    identification_document_code = serializers.ChoiceField(
        choices=User.DocumentType.choices,
    )
    identification_number = serializers.RegexField(
        r"^[A-Za-z0-9.-]+$",
        max_length=20,
    )
    telephone = serializers.RegexField(
        r"^\+?[0-9 ()-]{7,20}$",
        max_length=20,
        allow_blank=True,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "identification_document_code",
            "identification_number",
            "name",
            "email",
            "telephone",
        )
        read_only_fields = ("id",)

    def validate_email(self, value):
        value = value.strip().lower()
        queryset = User.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Este correo electrónico ya está registrado."
            )
        return value

    def validate_name(self, value):
        value = " ".join(value.strip().split())
        if not value:
            raise serializers.ValidationError(
                "El nombre no puede estar vacío."
            )
        return value

    def validate_identification_number(self, value):
        value = value.strip()
        queryset = User.objects.filter(
            identification_number__iexact=value
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Este número de identificación ya está registrado."
            )
        return value

    def create(self, validated_data):
        validated_data["username"] = (
            "customer_" + validated_data["identification_number"]
        )
        validated_data["role"] = User.Role.CLIENT
        user = User(**validated_data)
        user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.first_name = validated_data.pop(
            "first_name",
            instance.first_name,
        )
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.role = User.Role.CLIENT
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = " ".join(
            part for part in (instance.first_name, instance.last_name) if part
        )
        return data
