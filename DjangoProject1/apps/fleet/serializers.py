from rest_framework import serializers

from DjangoProject1.apps.accounts.models import User
from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, Seat


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
    class Meta:
        model = Driver
        fields = "__all__"
        
    def validate_user(self, user):
        if user.role != User.Role.DRIVER:
            raise serializers.ValidationError(
                f"El usuario {user.username} con ID {user.id} debe tener el rol "
                f"'{User.Role.DRIVER}'. Rol actual: '{user.role}'."
            )
        return user


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = "__all__"
