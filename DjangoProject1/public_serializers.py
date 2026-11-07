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
    state_source = serializers.CharField(read_only=True)
    automatic_completion_at = serializers.SerializerMethodField()
    sales_close_at = serializers.SerializerMethodField()
    can_sell = serializers.SerializerMethodField()
    sales_block_reason = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = (
            "id",
            "route",
            "date_time_start",
            "date_time_end",
            "trip_state",
            "state_source",
            "automatic_completion_at",
            "sales_close_at",
            "can_sell",
            "sales_block_reason",
            "server_time",
            "fare_amount_cents",
            "currency",
        )

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

    def get_fare_amount_cents(self, trip):
        fare = getattr(trip, "fare", None)
        return fare.amount_cents if fare else None

    def get_currency(self, trip):
        return "COP"
