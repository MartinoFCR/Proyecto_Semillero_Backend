from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

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
        filters = {
            "trip_state": Trip.TripState.SCHEDULED,
            "date_time_start__gte": timezone.now(),
        }
        origin = self.request.query_params.get("origin")
        destination = self.request.query_params.get("destination")
        date = self.request.query_params.get("date")
        if origin:
            filters["route__origin_id"] = origin
        if destination:
            filters["route__destination_id"] = destination
        if date:
            filters["date_time_start__date"] = date
        return (
            Trip.objects.filter(**filters)
            .select_related(
                "route__origin__city__department",
                "route__destination__city__department",
                "fare",
            )
            .order_by("date_time_start", "id")
        )


class CustomerServiceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "email": getattr(settings, "CUSTOMER_SERVICE_EMAIL", None),
            "phone": getattr(settings, "CUSTOMER_SERVICE_PHONE", None),
            "whatsapp": getattr(settings, "CUSTOMER_SERVICE_WHATSAPP", None),
            "business_hours": getattr(settings, "CUSTOMER_SERVICE_HOURS", None),
            "timezone": settings.TIME_ZONE,
            "changes_policy_url": getattr(settings, "CHANGES_POLICY_URL", None),
            "refunds_policy_url": getattr(settings, "REFUNDS_POLICY_URL", None),
            "privacy_policy_url": getattr(settings, "PRIVACY_POLICY_URL", None),
            "terms_url": getattr(settings, "TERMS_URL", None),
        })
