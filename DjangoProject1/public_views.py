from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.trips.models import Trip
from DjangoProject1.public_serializers import (
    PublicRouteSerializer,
    PublicTripSerializer,
)


class PublicRouteListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicRouteSerializer
    queryset = Route.objects.select_related(
        "origin__city__department",
        "destination__city__department",
    ).order_by("origin__place_name", "destination__place_name", "id")


class PublicTripListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicTripSerializer

    def get_queryset(self):
        return (
            Trip.objects.filter(
                trip_state=Trip.TripState.SCHEDULED,
                date_time_start__gte=timezone.now(),
            )
            .select_related(
                "route__origin__city__department",
                "route__destination__city__department",
                "fare",
            )
            .order_by("date_time_start", "id")
        )
