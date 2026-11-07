from django.db import connection
from django.utils import timezone
from rest_framework import status
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
        import datetime
        from django.db.models import Q
        from DjangoProject1.apps.trips.trip_state_services import get_server_now

        now = get_server_now()
        # Ventana de venta permitida: hasta 10 minutos después de la salida
        # Por tanto, date_time_start + 10 min >= now  <=>  date_time_start >= now - 10 min
        min_start_time = now - datetime.timedelta(minutes=10)

        # Incluir viajes vendibles en scheduled o in_progress dentro de la ventana de 10 min
        queryset = Trip.objects.filter(
            trip_state__in=[Trip.TripState.SCHEDULED, Trip.TripState.IN_PROGRESS],
            date_time_start__gte=min_start_time,
        ).exclude(
            trip_state__in=[Trip.TripState.COMPLETED, Trip.TripState.CANCELLED],
        )

        origin = self.request.query_params.get("origin")
        destination = self.request.query_params.get("destination")
        date = self.request.query_params.get("date")
        if origin:
            queryset = queryset.filter(route__origin_id=origin)
        if destination:
            queryset = queryset.filter(route__destination_id=destination)
        if date:
            queryset = queryset.filter(date_time_start__date=date)

        return (
            queryset.select_related(
                "route__origin__city__department",
                "route__destination__city__department",
                "fare",
                "bus",
            ).order_by("date_time_start", "id")
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


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = True
        error_msg = ""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
        except Exception as exc:
            db_ok = False
            error_msg = str(exc)

        payload = {
            "status": "healthy" if db_ok else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
            "server_time": timezone.now(),
        }
        if not db_ok:
            payload["error"] = error_msg
            return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(payload, status=status.HTTP_200_OK)
