from django.db import transaction
from rest_framework import serializers

from DjangoProject1.apps.accounts.models import User
from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, Seat


class DriverUserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "identification_number",
            "identification_document_code",
            "role",
        )
        read_only_fields = fields


class BusTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusType
        fields = "__all__"
        read_only_fields = ("id",)

    def validate_max_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La capacidad máxima debe ser mayor que cero."
            )
        return value


class BusSerializer(serializers.ModelSerializer):
    bus_type_detail = BusTypeSerializer(source="bus_type", read_only=True)

    class Meta:
        model = Bus
        fields = "__all__"
        extra_fields = ("bus_type_detail",)

    def get_fields(self):
        fields = super().get_fields()
        fields["bus_type_detail"] = BusTypeSerializer(
            source="bus_type",
            read_only=True,
        )
        return fields

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La capacidad debe ser mayor que cero."
            )
        return value

    def validate(self, attrs):
        capacity = attrs.get(
            "capacity",
            self.instance.capacity if self.instance else None,
        )
        bus_type = attrs.get(
            "bus_type",
            self.instance.bus_type if self.instance else None,
        )
        if bus_type and capacity > bus_type.max_capacity:
            raise serializers.ValidationError({
                "capacity": (
                    f"La capacidad no puede superar {bus_type.max_capacity} "
                    f"para el tipo '{bus_type.name}'."
                )
            })
        return attrs

class DriverSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
    )
    user_detail = DriverUserSummarySerializer(source="user", read_only=True)

    # Campos opcionales para crear o enlazar la cuenta de usuario automáticamente
    email = serializers.EmailField(
        required=False,
        write_only=True,
        allow_blank=True,
    )
    identification_number = serializers.CharField(
        required=False,
        write_only=True,
        max_length=20,
        allow_blank=True,
    )
    identification_document_code = serializers.ChoiceField(
        choices=User.DocumentType.choices,
        required=False,
        write_only=True,
        default=User.DocumentType.CC,
    )
    password = serializers.CharField(
        required=False,
        write_only=True,
        allow_blank=True,
    )

    class Meta:
        model = Driver
        fields = (
            "id",
            "full_name",
            "license_number",
            "address",
            "phone_number",
            "user",
            "user_detail",
            "email",
            "identification_number",
            "identification_document_code",
            "password",
        )

    def validate_user(self, user):
        if user and user.role != User.Role.DRIVER:
            raise serializers.ValidationError(
                f"El usuario {user.username} con ID {user.id} debe tener el rol "
                f"'{User.Role.DRIVER}'. Rol actual: '{user.role}'."
            )
        return user

    def validate(self, attrs):
        user = attrs.get("user")
        if self.instance is None and not user:
            # Creación unificada: requiere al menos identificación o email si no se proporciona user_id
            ident = attrs.get("identification_number", "").strip()
            email = attrs.get("email", "").strip().lower()

            if not ident:
                raise serializers.ValidationError({
                    "identification_number": (
                        "Es obligatorio proporcionar el número de identificación del conductor "
                        "o seleccionar un usuario existente."
                    )
                })

            if not email:
                raise serializers.ValidationError({
                    "email": "El correo electrónico es obligatorio para crear la cuenta del conductor."
                })

            # Validar que el email no esté en uso por otro usuario
            if User.objects.filter(email__iexact=email).exists():
                existing_by_email = User.objects.get(email__iexact=email)
                if existing_by_email.role != User.Role.DRIVER:
                    raise serializers.ValidationError({
                        "email": f"El correo {email} ya pertenece a un usuario con rol '{existing_by_email.role}'."
                    })
                if hasattr(existing_by_email, "driver_profile"):
                    raise serializers.ValidationError({
                        "email": f"El usuario asociado a {email} ya tiene un perfil de conductor registrado."
                    })

            # Validar que la identificación no esté en uso por otro usuario
            if User.objects.filter(identification_number__iexact=ident).exists():
                existing_by_ident = User.objects.get(identification_number__iexact=ident)
                if existing_by_ident.role != User.Role.DRIVER:
                    raise serializers.ValidationError({
                        "identification_number": (
                            f"La identificación {ident} ya pertenece a un usuario con rol '{existing_by_ident.role}'."
                        )
                    })
                if hasattr(existing_by_ident, "driver_profile"):
                    raise serializers.ValidationError({
                        "identification_number": (
                            f"La identificación {ident} ya tiene un perfil de conductor registrado."
                        )
                    })

        return attrs

    def create(self, validated_data):
        user = validated_data.pop("user", None)
        email = validated_data.pop("email", "").strip().lower()
        ident = validated_data.pop("identification_number", "").strip()
        doc_code = validated_data.pop("identification_document_code", User.DocumentType.CC)
        password = validated_data.pop("password", "").strip()

        with transaction.atomic():
            if not user:
                # Buscar si ya existe un usuario conductor con esa identificación o email
                existing_user = User.objects.filter(
                    identification_number__iexact=ident,
                    role=User.Role.DRIVER,
                ).first() or User.objects.filter(
                    email__iexact=email,
                    role=User.Role.DRIVER,
                ).first()

                if existing_user:
                    user = existing_user
                else:
                    # Crear nuevo usuario con rol DRIVER
                    full_name = validated_data.get("full_name", "").strip()
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else "Conductor"
                    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

                    # Generar username único a partir del documento o email
                    base_username = f"driver_{ident}" if ident else email.split("@")[0]
                    username = base_username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}_{counter}"
                        counter += 1

                    user = User.objects.create(
                        username=username,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        identification_number=ident,
                        identification_document_code=doc_code,
                        telephone=validated_data.get("phone_number", ""),
                        role=User.Role.DRIVER,
                        password_change_required=True,
                    )
                    # Contraseña por defecto (la identificación) o la indicada
                    init_password = password if password else ident
                    user.set_password(init_password)
                    user.save()

            validated_data["user"] = user
            return super().create(validated_data)


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = "__all__"
