from rest_framework import serializers

from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.trips.models import Trip


class PublicPlaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="place_name")
    city = serializers.SerializerMethodField()

    def get_city(self, place):
        return {
            "id": place.city_id,
            "name": place.city.city_name,
            "department": {
                "id": place.city.department_id,
                "name": place.city.department.department_name,
            },
        }


class PublicRouteSerializer(serializers.ModelSerializer):
    origin = PublicPlaceSerializer()
    destination = PublicPlaceSerializer()

    class Meta:
        model = Route
        fields = ("id", "origin", "destination", "distance_km")


class PublicTripSerializer(serializers.ModelSerializer):
    route = PublicRouteSerializer()
    fare_amount_cents = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = (
            "id",
            "route",
            "date_time_start",
            "date_time_end",
            "trip_state",
            "fare_amount_cents",
            "currency",
        )

    def get_fare_amount_cents(self, trip):
        fare = getattr(trip, "fare", None)
        return fare.amount_cents if fare else None

    def get_currency(self, trip):
        return "COP"
