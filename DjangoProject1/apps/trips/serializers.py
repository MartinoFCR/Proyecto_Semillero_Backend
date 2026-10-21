from rest_framework import serializers

from DjangoProject1.apps.trips.models import (
    CurrentSeatState,
    Event,
    Reading,
    SeatsStateRecord,
    Trip,
)
from DjangoProject1.serializers import GeoJSONPointField


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = "__all__"


class ReadingSerializer(serializers.ModelSerializer):
    reading_point = GeoJSONPointField()

    class Meta:
        model = Reading
        fields = "__all__"


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
