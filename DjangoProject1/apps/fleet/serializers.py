from rest_framework import serializers

from DjangoProject1.apps.accounts.models import User
from DjangoProject1.apps.fleet.models import Bus, Driver, Seat


class BusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = "__all__"

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La capacidad debe ser mayor que cero."
            )
        return value

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
