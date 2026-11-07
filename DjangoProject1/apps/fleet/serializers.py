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
    class Meta:
        model = Driver
        fields = (
            "id",
            "full_name",
            "license_number",
            "address",
            "phone_number",
            "is_active",
        )

    def validate_full_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("El nombre completo es obligatorio.")
        return val

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
