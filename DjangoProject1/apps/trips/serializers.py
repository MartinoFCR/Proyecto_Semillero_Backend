from rest_framework import serializers

from DjangoProject1.apps.trips.models import (
    CurrentSeatState,
    Event,
    Reading,
    SeatsStateRecord,
    Trip,
    TripFare,
)
from DjangoProject1.serializers import GeoJSONPointField



class TripSerializer(serializers.ModelSerializer):
    fare_amount_cents = serializers.SerializerMethodField()
    origin = serializers.CharField(source="route.origin.place_name", read_only=True)
    destination = serializers.CharField(
        source="route.destination.place_name",
        read_only=True,
    )

    class Meta:
        model = Trip
        fields = "__all__"
        read_only_fields = ("id",)

    def get_fare_amount_cents(self, obj):
        fare = getattr(obj, "fare", None)
        return fare.amount_cents if fare else None

    def validate(self, attrs):
        instance = self.instance

        start = attrs.get(
            "date_time_start",
            instance.date_time_start if instance else None
        )
        end = attrs.get(
            "date_time_end",
            instance.date_time_end if instance else None
        )

        odometer_start = attrs.get(
            "odometer_start",
            instance.odometer_start if instance else None
        )
        odometer_end = attrs.get(
            "odometer_end",
            instance.odometer_end if instance else None
        )

        if start and end and end < start:
            raise serializers.ValidationError({
                "date_time_end":
                    "La fecha final no puede ser anterior a la inicial."
            })

        if (
            odometer_start is not None
            and odometer_end is not None
            and odometer_end < odometer_start
        ):
            raise serializers.ValidationError({
                "odometer_end":
                    "El odómetro final no puede ser inferior al inicial."
            })

        return attrs


class TripFareSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripFare
        fields = "__all__"
        read_only_fields = ("id", "updated_at")

    def validate_amount_cents(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La tarifa debe ser mayor que cero."
            )
        return value


class ReadingSerializer(serializers.ModelSerializer):
    reading_point = GeoJSONPointField()

    class Meta:
        model = Reading
        fields = "__all__"

    def validate_speed(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "La velocidad no puede ser negativa."
            )
        return value

    def validate_fuel_level(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "El combustible debe estar entre 0 y 100."
            )
        return value


class EventSerializer(serializers.ModelSerializer):
    event_point = GeoJSONPointField()

    class Meta:
        model = Event
        fields = "__all__"


class CurrentSeatStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentSeatState
        fields = "__all__"


class SeatsStateRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatsStateRecord
        fields = "__all__"
