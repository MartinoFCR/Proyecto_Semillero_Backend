from django.db import transaction
from rest_framework import serializers

from DjangoProject1.apps.fleet.models import Bus
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
    fare_amount_cents = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    origin = serializers.CharField(source="route.origin.place_name", read_only=True)
    destination = serializers.CharField(
        source="route.destination.place_name",
        read_only=True,
    )
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    bus_plate = serializers.CharField(source="bus.plate", read_only=True)
    state_source = serializers.CharField(read_only=True)
    manual_operator_detail = serializers.SerializerMethodField()
    state_attribution_message = serializers.SerializerMethodField()
    automatic_completion_at = serializers.SerializerMethodField()
    sales_close_at = serializers.SerializerMethodField()
    can_sell = serializers.SerializerMethodField()
    sales_block_reason = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = "__all__"
        read_only_fields = (
            "id",
            "state_source",
            "manual_operator",
            "manual_operator_detail",
            "manual_action_at",
            "cancellation_reason",
            "state_attribution_message",
            "automatic_completion_at",
            "sales_close_at",
            "can_sell",
            "sales_block_reason",
            "server_time",
        )

    def get_manual_operator_detail(self, trip):
        op = getattr(trip, "manual_operator", None)
        if not op:
            return None
        from DjangoProject1.apps.support.audit import format_user_attribution
        role_code, role_label, full_name = format_user_attribution(op)
        return {
            "id": op.id,
            "username": op.username,
            "name": full_name,
            "role": role_code,
            "role_label": role_label,
            "signature": f"ATT: {role_label} {full_name}",
        }

    def get_state_attribution_message(self, trip):
        from DjangoProject1.apps.support.audit import build_att_signature
        op = getattr(trip, "manual_operator", None)
        action_time = ""
        if trip.manual_action_at:
            from django.utils import timezone
            local_dt = timezone.localtime(trip.manual_action_at)
            action_time = f" el {local_dt.strftime('%d/%m/%Y a las %H:%M')}"

        if trip.trip_state == Trip.TripState.COMPLETED:
            if op:
                sig = build_att_signature(op)
                return f"Este viaje fue finalizado{action_time} — {sig}"
            return "Este viaje fue finalizado automáticamente por cumplimiento de horario programado."
        if trip.trip_state == Trip.TripState.CANCELLED:
            reason_part = f" (Motivo: {trip.cancellation_reason})" if trip.cancellation_reason else ""
            if op:
                sig = build_att_signature(op)
                return f"Este viaje fue cancelado{action_time}{reason_part} — {sig}"
            return f"Este viaje fue cancelado{reason_part}."
        if trip.trip_state == Trip.TripState.IN_PROGRESS:
            return f"Viaje en curso — Conductor asignado: {trip.driver.full_name}"
        return f"Viaje programado — Conductor asignado: {trip.driver.full_name}"

    def _get_sales_meta(self, trip):
        if not hasattr(trip, "_cached_sales_meta"):
            from DjangoProject1.apps.trips.trip_state_services import compute_trip_sales_availability
            trip._cached_sales_meta = compute_trip_sales_availability(trip)
        return trip._cached_sales_meta

    def get_automatic_completion_at(self, trip):
        return self._get_sales_meta(trip)["automatic_completion_at"]

    def get_sales_close_at(self, trip):
        return self._get_sales_meta(trip)["sales_close_at"]

    def get_can_sell(self, trip):
        return self._get_sales_meta(trip)["can_sell"]

    def get_sales_block_reason(self, trip):
        return self._get_sales_meta(trip)["sales_block_reason"]

    def get_server_time(self, trip):
        return self._get_sales_meta(trip)["server_time"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        fare = getattr(instance, "fare", None)
        data["fare_amount_cents"] = fare.amount_cents if fare else None
        return data

    def validate_fare_amount_cents(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("La tarifa del viaje debe ser mayor que cero.")
        return value

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

        # 1. Validación del Bus (Estado activo y no solapamiento)
        bus = attrs.get("bus", instance.bus if instance else None)
        if bus:
            if bus.state != Bus.State.ACTIVE:
                raise serializers.ValidationError({
                    "bus": f"El bus '{bus.plate}' no está activo (estado actual: '{bus.state}')."
                })

            if start:
                overlapping_bus_trips = Trip.objects.filter(
                    bus=bus,
                    trip_state__in=[Trip.TripState.SCHEDULED, Trip.TripState.IN_PROGRESS],
                )
                if instance:
                    overlapping_bus_trips = overlapping_bus_trips.exclude(pk=instance.pk)

                if end:
                    overlapping_bus_trips = overlapping_bus_trips.filter(
                        date_time_start__lt=end,
                        date_time_end__gt=start,
                    )
                else:
                    overlapping_bus_trips = overlapping_bus_trips.filter(
                        date_time_start=start,
                    )

                if overlapping_bus_trips.exists():
                    raise serializers.ValidationError({
                        "bus": (
                            f"El bus '{bus.plate}' ya tiene asignado otro viaje activo "
                            f"en este mismo horario."
                        )
                    })

        # 2. Validación de solapamiento de horario para el conductor
        driver = attrs.get("driver", instance.driver if instance else None)
        if driver:
            if not driver.is_active:
                raise serializers.ValidationError({
                    "driver": f"El conductor '{driver.full_name}' se encuentra inactivo y no puede ser asignado a viajes."
                })

            if start:
                overlapping_trips = Trip.objects.filter(
                    driver=driver,
                    trip_state__in=[Trip.TripState.SCHEDULED, Trip.TripState.IN_PROGRESS],
                )
                if instance:
                    overlapping_trips = overlapping_trips.exclude(pk=instance.pk)

                if end:
                    overlapping_trips = overlapping_trips.filter(
                        date_time_start__lt=end,
                        date_time_end__gt=start,
                    )
                else:
                    overlapping_trips = overlapping_trips.filter(
                        date_time_start=start,
                    )

                if overlapping_trips.exists():
                    raise serializers.ValidationError({
                        "driver": (
                            f"El conductor '{driver.full_name}' ya tiene asignado otro viaje activo "
                            f"en este mismo horario."
                        )
                    })

        return attrs

    def create(self, validated_data):
        from DjangoProject1.apps.trips.trip_state_services import compute_trip_operational_state
        fare_cents = validated_data.pop("fare_amount_cents", None)
        # El estado operativo se calcula y asigna automáticamente al crear
        initial_state, _ = compute_trip_operational_state(Trip(**validated_data))
        validated_data["trip_state"] = initial_state
        validated_data["state_source"] = "automatic"

        with transaction.atomic():
            trip = super().create(validated_data)
            if fare_cents is not None:
                TripFare.objects.update_or_create(
                    trip=trip,
                    defaults={"amount_cents": fare_cents},
                )
            return trip

    def update(self, instance, validated_data):
        fare_cents = validated_data.pop("fare_amount_cents", None)
        with transaction.atomic():
            trip = super().update(instance, validated_data)
            if fare_cents is not None:
                TripFare.objects.update_or_create(
                    trip=trip,
                    defaults={"amount_cents": fare_cents},
                )
            return trip


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
