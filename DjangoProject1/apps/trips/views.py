
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.utils import timezone
from DjangoProject1.apps.fleet.services import complete_seats_for_bus
from DjangoProject1.apps.sales.models import Sale, SaleItem, Ticket

from DjangoProject1.apps.trips.models import (
    Trip,
    Reading,
    Event,
    CurrentSeatState,
    SeatsStateRecord,
    TripFare,
)
from DjangoProject1.apps.trips.serializers import (
    TripSerializer,
    ReadingSerializer,
    EventSerializer,
    CurrentSeatStateSerializer,
    SeatsStateRecordSerializer,
    TripFareSerializer,
)
from DjangoProject1.permissions import (
    IsAdminRole,
    IsAdminOrReadOnly,
    IsAdminOrAssignedDriverReadOnly,
    IsAdminOrAssignedDriver,
)


class TripViewSet(ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            return [IsAdminRole()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Trip.objects.select_related(
            "bus",
            "driver",
            "route",
            "route__origin",
            "route__destination",
            "fare",
        ).order_by("-date_time_start", "id")

        user_role = getattr(self.request.user, "role", None)

        if user_role == "client":
            queryset = queryset.filter(
                trip_state=Trip.TripState.SCHEDULED,
            )

        # Filtros administrativos y de consulta
        route_id = self.request.query_params.get("route")
        bus_id = self.request.query_params.get("bus")
        driver_id = self.request.query_params.get("driver")
        state = self.request.query_params.get("state")
        date_str = self.request.query_params.get("date")

        if route_id:
            queryset = queryset.filter(route_id=route_id)
        if bus_id:
            queryset = queryset.filter(bus_id=bus_id)
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        if state:
            queryset = queryset.filter(trip_state=state)
        if date_str:
            queryset = queryset.filter(date_time_start__date=date_str)

        return queryset


class TripFareViewSet(ModelViewSet):
    queryset = TripFare.objects.select_related("trip").all()
    serializer_class = TripFareSerializer
    permission_classes = [IsAdminOrReadOnly]


class AvailableSeatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, trip_id):
        try:
            trip = Trip.objects.select_related("bus").get(
                pk=trip_id,
                trip_state=Trip.TripState.SCHEDULED,
            )
        except Trip.DoesNotExist:
            return Response(
                {"detail": "Viaje no encontrado o no disponible."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            if trip.bus.seats.count() < trip.bus.capacity:
                complete_seats_for_bus(trip.bus, trip.bus.capacity)
        except Exception as exc:
            pass

        now = timezone.now()
        Sale.objects.filter(
            trip=trip,
            source=Sale.Source.ONLINE,
            status=Sale.Status.PENDING,
            expires_at__lte=now,
        ).update(
            status=Sale.Status.EXPIRED,
            updated_at=now,
        )
        issued_seats = set(
            Ticket.objects.filter(
                trip=trip,
                status=Ticket.Status.ISSUED,
            ).values_list("seat_id", flat=True)
        )
        held_seats = set(
            Sale.objects.filter(
                trip=trip,
                source=Sale.Source.ONLINE,
                status=Sale.Status.PENDING,
            ).values_list("seat_id", flat=True)
        )
        held_seats.update(
            SaleItem.objects.filter(
                sale__trip=trip,
                sale__source=Sale.Source.ONLINE,
                sale__status=Sale.Status.PENDING,
            ).values_list("seat_id", flat=True)
        )
        all_seats = list(trip.bus.seats.all())
        all_seats.sort(
            key=lambda s: (
                int(s.row) if str(s.row).isdigit() else 0,
                int(s.col) if str(s.col).isdigit() else 0,
                int(s.seat_number) if str(s.seat_number).isdigit() else 0,
            )
        )
        seats = []
        for seat in all_seats:
            if seat.id in issued_seats:
                state = "sold"
            elif seat.id in held_seats:
                state = "reserved"
            else:
                state = "available"
            seats.append({
                "id": seat.id,
                "seat_number": seat.seat_number,
                "row": seat.row,
                "col": seat.col,
                "status": state,
            })
        return Response({
            "trip": trip.id,
            "server_time": now,
            "seats": seats,
        })


class ReadingViewSet(ModelViewSet):
    serializer_class = ReadingSerializer
    permission_classes = [IsAdminOrAssignedDriver]

    def get_queryset(self):
        queryset = Reading.objects.select_related("trip")

        if self.request.user.role == "admin":
            return queryset.all()

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(trip__driver=driver_profile)

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]

        if self.request.user.role == "admin":
            serializer.save()
            return

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if not driver_profile or trip.driver_id != driver_profile.pk:
            raise PermissionDenied(
                "No puedes registrar lecturas para este viaje."
            )

        serializer.save()


class EventViewSet(ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrAssignedDriver]

    def get_queryset(self):
        queryset = Event.objects.select_related("trip")

        if self.request.user.role == "admin":
            return queryset.all()

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(trip__driver=driver_profile)

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]

        if self.request.user.role == "admin":
            serializer.save()
            return

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if not driver_profile or trip.driver_id != driver_profile.pk:
            raise PermissionDenied(
                "No puedes registrar eventos para este viaje."
            )

        serializer.save()


class CurrentSeatStateViewSet(ReadOnlyModelViewSet):
    serializer_class = CurrentSeatStateSerializer
    permission_classes = [IsAdminOrAssignedDriver]

    def get_queryset(self):
        queryset = CurrentSeatState.objects.select_related(
            "trip",
            "trip__driver",
            "seat",
            "seat__bus",
        )

        if self.request.user.role == "admin":
            return queryset.all()

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(trip__driver=driver_profile)


class SeatsStateRecordViewSet(ReadOnlyModelViewSet):
    serializer_class = SeatsStateRecordSerializer
    permission_classes = [IsAdminOrAssignedDriver]

    def get_queryset(self):
        queryset = SeatsStateRecord.objects.select_related(
            "trip",
            "trip__driver",
            "seat",
            "seat__bus",
        )

        if self.request.user.role == "admin":
            return queryset.all()

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(trip__driver=driver_profile)


class TelemetryIngestView(APIView):
    """Endpoint HTTP para recibir telemetría de dispositivos GPS/ESP32.

    Permite tanto el puente desde un broker MQTT como pruebas directas de ingesta.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from DjangoProject1.apps.trips.telemetry_services import ingest_device_telemetry

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": "El cuerpo de la solicitud debe ser un objeto JSON."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ingest_device_telemetry(data)
            return Response(result, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            msg = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": f"Error al procesar telemetría: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
