from rest_framework import serializers

from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, GPSDevice, Seat


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


class GPSDeviceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = GPSDevice
        fields = ("id", "name", "device_id", "model", "state", "last_ping_at")
        read_only_fields = fields


class BusSerializer(serializers.ModelSerializer):
    bus_type_detail = BusTypeSerializer(source="bus_type", read_only=True)
    gps_device_detail = GPSDeviceSummarySerializer(source="gps_device", read_only=True)

    class Meta:
        model = Bus
        fields = "__all__"
        extra_fields = ("bus_type_detail", "gps_device_detail")

    def get_fields(self):
        fields = super().get_fields()
        fields["bus_type_detail"] = BusTypeSerializer(
            source="bus_type",
            read_only=True,
        )
        fields["gps_device_detail"] = GPSDeviceSummarySerializer(
            source="gps_device",
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
    full_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    photo_url = serializers.SerializerMethodField(read_only=True)
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    class Meta:
        model = Driver
        fields = (
            "id",
            "full_name",
            "first_name",
            "last_name",
            "document_type",
            "document_number",
            "birth_date",
            "email",
            "phone_number",
            "address",
            "password",
            "license_number",
            "license_category",
            "license_expiry",
            "experience_years",
            "blood_group",
            "operational_status",
            "photo",
            "photo_url",
            "is_active",
            "has_medical_exam",
            "has_psychosensometric_test",
            "has_clean_driving_record",
            "has_first_aid_training",
            "user",
            "username",
            "user_email",
        )
        read_only_fields = ("id", "photo_url", "user", "username", "user_email")

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        try:
            if not obj.photo.storage.exists(obj.photo.name):
                return None
        except Exception:
            pass
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url

    def validate_license_number(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("El número de licencia es obligatorio.")
        qs = Driver.objects.filter(license_number__iexact=val)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un conductor con esta licencia de conducción.")
        return val

    def validate(self, attrs):
        first_name = (attrs.get("first_name") if "first_name" in attrs else (self.instance.first_name if self.instance else "")) or ""
        last_name = (attrs.get("last_name") if "last_name" in attrs else (self.instance.last_name if self.instance else "")) or ""
        full_name = (attrs.get("full_name") if "full_name" in attrs else (self.instance.full_name if self.instance else "")) or ""

        first_name = first_name.strip()
        last_name = last_name.strip()
        full_name = full_name.strip()

        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()
            attrs["full_name"] = full_name
        elif full_name and not first_name:
            parts = " ".join(full_name.split()).split(" ", 1)
            attrs["first_name"] = parts[0]
            if len(parts) > 1 and not last_name:
                attrs["last_name"] = parts[1]
            attrs["full_name"] = full_name
        elif full_name:
            attrs["full_name"] = full_name

        if not attrs.get("full_name") and not (self.instance and self.instance.full_name):
            raise serializers.ValidationError({"full_name": "El nombre completo es obligatorio."})

        if "first_name" in attrs:
            attrs["first_name"] = attrs["first_name"].strip()
        if "last_name" in attrs:
            attrs["last_name"] = attrs["last_name"].strip()

        return attrs

    def _sync_driver_user(self, driver, password=None):
        """Crea o sincroniza la cuenta de usuario con rol 'driver' para que el conductor pueda iniciar sesión."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        User = get_user_model()

        doc_type_map = {
            "CC": User.DocumentType.CC,
            "DNI": User.DocumentType.CC,
            "CE": User.DocumentType.CE,
            "PASSPORT": User.DocumentType.PASSPORT,
        }
        user_doc_code = doc_type_map.get(driver.document_type, User.DocumentType.CC)
        raw_identifier = (driver.document_number or "").strip() or driver.license_number.strip()
        ident_number = raw_identifier[:20]

        first_name = (driver.first_name or "").strip()
        last_name = (driver.last_name or "").strip()
        if not first_name and driver.full_name:
            parts = " ".join(driver.full_name.strip().split()).split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        driver_email = (driver.email or "").strip().lower()
        clean_pw = (password or "").strip() if password is not None else ""

        user = driver.user
        if user is None:
            user = User.objects.filter(identification_number__iexact=ident_number).first()
            if user is None and driver_email:
                user = User.objects.filter(email__iexact=driver_email).first()

            if user is None:
                resolved_email = driver_email
                if not resolved_email or User.objects.filter(email__iexact=resolved_email).exists():
                    resolved_email = f"driver.{ident_number.lower()}@portalbic.site"
                resolved_email = resolved_email[:50]

                base_username = f"driver_{ident_number}"
                username = base_username
                counter = 1
                while User.objects.filter(username__iexact=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                request = self.context.get("request")
                creator = (
                    request.user
                    if (request and getattr(request, "user", None) and request.user.is_authenticated)
                    else None
                )
                user = User(
                    username=username,
                    email=resolved_email,
                    identification_document_code=user_doc_code,
                    identification_number=ident_number,
                    first_name=first_name,
                    last_name=last_name,
                    telephone=(driver.phone_number or "")[:20],
                    role=User.Role.DRIVER,
                    is_active=driver.is_active,
                    created_by=creator,
                )
                if clean_pw:
                    user.set_password(clean_pw)
                    user.password_change_required = False
                else:
                    user.set_password(raw_identifier)
                    user.password_change_required = True
                user.save()
            else:
                if clean_pw:
                    user.set_password(clean_pw)
                    user.password_change_required = False
                    user.password_changed_at = timezone.now()
                    user.save(update_fields=["password", "password_change_required", "password_changed_at"])

            driver.user = user
            if not driver.email and user.email:
                driver.email = user.email
                driver.save(update_fields=["user", "email"])
            else:
                driver.save(update_fields=["user"])
        else:
            update_fields = [
                "first_name",
                "last_name",
                "telephone",
                "is_active",
                "identification_document_code",
            ]
            user.first_name = first_name
            user.last_name = last_name
            user.telephone = (driver.phone_number or "")[:20]
            user.is_active = driver.is_active
            user.identification_document_code = user_doc_code

            if (
                ident_number
                and user.identification_number != ident_number
                and not User.objects.filter(identification_number__iexact=ident_number).exclude(pk=user.pk).exists()
            ):
                user.identification_number = ident_number
                update_fields.append("identification_number")

            if (
                driver_email
                and user.email != driver_email
                and not User.objects.filter(email__iexact=driver_email).exclude(pk=user.pk).exists()
            ):
                user.email = driver_email[:50]
                update_fields.append("email")

            if clean_pw:
                user.set_password(clean_pw)
                user.password_change_required = False
                user.password_changed_at = timezone.now()
                update_fields.extend(["password", "password_change_required", "password_changed_at"])

            user.save(update_fields=update_fields)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        driver = super().create(validated_data)
        self._sync_driver_user(driver, password=password)
        return driver

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        driver = super().update(instance, validated_data)
        self._sync_driver_user(driver, password=password)
        return driver


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = "__all__"


class GPSDeviceSerializer(serializers.ModelSerializer):
    bus_plate = serializers.CharField(source="bus.plate", read_only=True)
    api_key = serializers.CharField(
        read_only=True,
        source="api_key_prefix",
        help_text="Prefijo público del token (ej. esp_live_...). La clave completa solo se muestra una vez al crear.",
    )
    raw_api_key = serializers.CharField(
        read_only=True,
        required=False,
        help_text="Clave en texto plano generada. ÚNICAMENTE visible al crear el dispositivo.",
    )

    class Meta:
        model = GPSDevice
        fields = (
            "id",
            "name",
            "device_id",
            "model",
            "state",
            "api_key",
            "raw_api_key",
            "bus",
            "bus_plate",
            "last_ping_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "bus_plate", "api_key", "raw_api_key", "last_ping_at", "created_at", "updated_at")

    def validate_device_id(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("El identificador del dispositivo (device_id) es obligatorio.")
        qs = GPSDevice.objects.filter(device_id__iexact=val)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"Ya existe un dispositivo registrado con el device_id '{val}'.")
        return val

    def validate_bus(self, bus):
        if bus:
            qs = GPSDevice.objects.filter(bus=bus)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                raise serializers.ValidationError(
                    f"El bus '{bus.plate}' ya tiene asignado el dispositivo '{existing.name}' ({existing.device_id})."
                )
        return bus
