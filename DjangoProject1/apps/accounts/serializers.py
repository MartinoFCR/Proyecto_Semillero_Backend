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
        
        if self.instance is None and not value:
            raise serializers.ValidationError({"username": "Este campo es obligatorio."})
        
        queryset = User.objects.filter(username__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
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

        queryset = User.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
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
        user.role = User.Role.CLIENT
        if "identification_number" in validated_data:
            user.set_password(validated_data["identification_number"])
            user.password_change_required = True  # Forzamos el rol a CLIENT para registros públicos.

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
        user.set_password(validated_data["identification_number"])
        user.is_active = True
        user.password_change_required = True
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


class PublicRegistrationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True, max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "identification_document_code",
            "identification_number",
            "name",
            "email",
            "telephone",
            "password",
        )
        read_only_fields = ("id",)

    def validate_name(self, value):
        value = " ".join(value.strip().split())
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("El correo ya está registrado.")
        return value

    def validate_identification_number(self, value):
        value = value.strip()
        if User.objects.filter(
            identification_number__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "El documento ya está registrado."
            )
        return value

    def create(self, validated_data):
        name = validated_data.pop("name")
        password = validated_data.pop("password")
        first_name, *last_name = name.split(" ", 1)
        identification_number = validated_data["identification_number"]
        user = User(
            username="customer_" + identification_number,
            first_name=first_name,
            last_name=last_name[0] if last_name else "",
            role=User.Role.CLIENT,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


class ProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="first_name", max_length=150)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "identification_document_code",
            "identification_number",
            "name",
            "last_name",
            "email",
            "telephone",
            "role",
            "photo_url",
            "password_change_required",
        )
        read_only_fields = (
            "id",
            "identification_document_code",
            "identification_number",
            "role",
            "photo_url",
            "password_change_required",
        )

    def get_photo_url(self, user):
        if not user.photo or not user.photo.storage.exists(user.photo.name):
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(user.photo.url) if request else user.photo.url


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer exclusivo para la gestión de usuarios administradores (rol 'admin')."""

    name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=150,
    )
    username = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    identification_document_code = serializers.ChoiceField(
        choices=User.DocumentType.choices,
        required=False,
        default=User.DocumentType.CC,
    )
    identification_number = serializers.RegexField(
        r"^[A-Za-z0-9.-]+$",
        max_length=20,
    )
    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )
    telephone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    created_by_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "identification_document_code",
            "identification_number",
            "name",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "is_active",
            "password_change_required",
            "created_by",
            "created_by_detail",
            "date_joined",
            "password",
        )
        read_only_fields = (
            "id",
            "role",
            "password_change_required",
            "created_by",
            "created_by_detail",
            "date_joined",
        )

    def get_created_by_detail(self, obj):
        creator = getattr(obj, "created_by", None)
        if not creator:
            return None
        full_name = " ".join(
            part for part in (creator.first_name, creator.last_name) if part
        )
        return {
            "id": creator.id,
            "username": creator.username,
            "name": full_name or creator.username,
            "email": creator.email,
            "identification_number": creator.identification_number,
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("El correo electrónico es obligatorio.")
        queryset = User.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value

    def validate_identification_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El número de identificación es obligatorio.")
        queryset = User.objects.filter(identification_number__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Este número de identificación ya está registrado.")
        return value

    def validate_username(self, value):
        value = value.strip()
        if not value:
            return value
        queryset = User.objects.filter(username__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Este nombre de usuario ya está registrado.")
        return value

    def validate(self, attrs):
        raw_name = (attrs.pop("name", "") or "").strip()
        first_name = (attrs.get("first_name") or "").strip()
        last_name = (attrs.get("last_name") or "").strip()

        if raw_name and not first_name:
            parts = " ".join(raw_name.split()).split(" ", 1)
            attrs["first_name"] = parts[0]
            if len(parts) > 1 and not last_name:
                attrs["last_name"] = parts[1]
        else:
            if "first_name" in attrs:
                attrs["first_name"] = first_name
            if "last_name" in attrs:
                attrs["last_name"] = last_name

        if self.instance is None and not attrs.get("first_name"):
            raise serializers.ValidationError(
                {"first_name": "El nombre del administrador es obligatorio."}
            )

        password = attrs.get("password")
        if password:
            candidate_data = {
                k: v
                for k, v in attrs.items()
                if k in {"username", "email", "first_name", "last_name", "identification_number"}
            }
            candidate_user = self.instance or User(**candidate_data)
            try:
                password_validation.validate_password(password, user=candidate_user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        identification_number = validated_data["identification_number"]
        username = (validated_data.get("username") or "").strip()
        if not username:
            base_username = f"admin_{identification_number}"
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
        validated_data["username"] = username
        validated_data["role"] = User.Role.ADMIN
        is_active = validated_data.pop("is_active", True)

        user = User(**validated_data)
        if password:
            user.set_password(password)
            user.password_change_required = False
        else:
            user.set_password(identification_number)
            user.password_change_required = True

        user.is_active = is_active
        user.is_staff = True
        user.is_superuser = False
        request = self.context.get("request")
        if request and getattr(request, "user", None) and request.user.is_authenticated:
            user.created_by = request.user
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            if field == "username" and not value:
                continue
            setattr(instance, field, value)
        instance.role = User.Role.ADMIN
        instance.is_staff = True
        if password:
            from django.utils import timezone
            instance.set_password(password)
            instance.password_changed_at = timezone.now()
            instance.password_change_required = False
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        full_name = " ".join(
            part for part in (instance.first_name, instance.last_name) if part
        )
        data["name"] = full_name or instance.username
        return data
