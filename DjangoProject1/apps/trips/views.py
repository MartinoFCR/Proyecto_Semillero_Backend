
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.utils import timezone
from DjangoProject1.apps.fleet.services import complete_seats_for_bus
from DjangoProject1.apps.sales.models import Sale, SaleItem, Ticket

from rest_framework.decorators import action
from DjangoProject1.apps.trips.trip_state_services import (
    get_server_now,
    compute_trip_operational_state,
    compute_trip_sales_availability,
)
from DjangoProject1.apps.trips.models import (
    Trip,
    TripPostponementHistory,
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

    @action(detail=True, methods=["post"], url_path="cancel", permission_classes=[IsAdminRole])
    def cancel_trip(self, request, pk=None):
        """Cancela un viaje manualmente. Cierra ventas de inmediato y registra motivo y operador."""
        trip = self.get_object()
        if trip.trip_state == Trip.TripState.CANCELLED:
            return Response(
                {"detail": "El viaje ya se encuentra cancelado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"reason": "El motivo de la cancelación es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = get_server_now()
        trip.trip_state = Trip.TripState.CANCELLED
        trip.state_source = "manual"
        trip.manual_operator = request.user
        trip.manual_action_at = now
        trip.cancellation_reason = reason
        trip.save(update_fields=[
            "trip_state",
            "state_source",
            "manual_operator",
            "manual_action_at",
            "cancellation_reason",
        ])

        return Response(
            {
                "detail": f"Viaje #{trip.id} cancelado exitosamente.",
                "trip": self.get_serializer(trip).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="complete", permission_classes=[IsAdminRole])
    def complete_trip(self, request, pk=None):
        """Finaliza un viaje manualmente antes de lo programado. Cierra ventas de inmediato."""
        trip = self.get_object()
        if trip.trip_state == Trip.TripState.COMPLETED:
            return Response(
                {"detail": "El viaje ya se encuentra finalizado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if trip.trip_state == Trip.TripState.CANCELLED:
            return Response(
                {"detail": "No se puede finalizar un viaje cancelado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = get_server_now()
        trip.trip_state = Trip.TripState.COMPLETED
        trip.state_source = "manual"
        trip.manual_operator = request.user
        trip.manual_action_at = now
        if not trip.date_time_end:
            trip.date_time_end = now
            trip.save(update_fields=["trip_state", "state_source", "manual_operator", "manual_action_at", "date_time_end"])
        else:
            trip.save(update_fields=["trip_state", "state_source", "manual_operator", "manual_action_at"])

        return Response(
            {
                "detail": f"Viaje #{trip.id} finalizado exitosamente.",
                "trip": self.get_serializer(trip).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="postpone", permission_classes=[IsAdminRole])
    def postpone_trip(self, request, pk=None):
        """Posterga un viaje a una nueva fecha/hora de salida y llegada opcional.
        
        Recalcula automáticamente el estado operativo y el cierre de ventas según el nuevo horario,
        conservando intactas todas las ventas, pagos, tiquetes y facturas existentes, y registrando
        el historial de la postergación.
        """
        from django.utils.dateparse import parse_datetime
        trip = self.get_object()

        if trip.trip_state in [Trip.TripState.COMPLETED, Trip.TripState.CANCELLED]:
            return Response(
                {"detail": f"No se puede postergar un viaje con estado '{trip.trip_state}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_start_raw = request.data.get("new_date_time_start")
        new_end_raw = request.data.get("new_date_time_end")
        reason = request.data.get("reason", "").strip()

        if not new_start_raw:
            return Response(
                {"new_date_time_start": "La nueva fecha/hora de salida es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not reason:
            return Response(
                {"reason": "El motivo de la postergación es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed_new_start = parse_datetime(new_start_raw)
        if not parsed_new_start:
            return Response(
                {"new_date_time_start": "Formato de fecha inválido (use ISO-8601)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(parsed_new_start):
            parsed_new_start = timezone.make_aware(parsed_new_start)

        parsed_new_end = None
        if new_end_raw:
            parsed_new_end = parse_datetime(new_end_raw)
            if not parsed_new_end:
                return Response(
                    {"new_date_time_end": "Formato de fecha de llegada inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if timezone.is_naive(parsed_new_end):
                parsed_new_end = timezone.make_aware(parsed_new_end)
            if parsed_new_end <= parsed_new_start:
                return Response(
                    {"new_date_time_end": "La llegada no puede ser anterior o igual a la salida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        now = get_server_now()
        previous_start = trip.date_time_start
        previous_end = trip.date_time_end

        # Recalcular estado operativo según el nuevo horario
        trip.date_time_start = parsed_new_start
        trip.date_time_end = parsed_new_end
        new_computed_state, _ = compute_trip_operational_state(trip, now)
        trip.trip_state = new_computed_state
        trip.state_source = "automatic"

        with transaction.atomic():
            trip.save(update_fields=["date_time_start", "date_time_end", "trip_state", "state_source"])
            TripPostponementHistory.objects.create(
                trip=trip,
                previous_start=previous_start,
                previous_end=previous_end,
                new_start=parsed_new_start,
                new_end=parsed_new_end,
                reason=reason,
                operator=request.user,
            )

        return Response(
            {
                "detail": f"Viaje #{trip.id} postergado exitosamente para {parsed_new_start.isoformat()}.",
                "trip": self.get_serializer(trip).data,
            },
            status=status.HTTP_200_OK,
        )



class TripFareViewSet(ModelViewSet):
    queryset = TripFare.objects.select_related("trip").all()
    serializer_class = TripFareSerializer
    permission_classes = [IsAdminOrReadOnly]


class AvailableSeatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, trip_id):
        now = get_server_now()
        try:
            trip = Trip.objects.select_related("bus", "fare").get(
                pk=trip_id,
                trip_state__in=[Trip.TripState.SCHEDULED, Trip.TripState.IN_PROGRESS],
            )
        except Trip.DoesNotExist:
            return Response(
                {"detail": "Viaje no encontrado o no disponible."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validar si el viaje tiene las ventas cerradas
        sales_meta = compute_trip_sales_availability(trip, now)
        if not sales_meta["can_sell"] and sales_meta["sales_block_reason"] == "sales_closed":
            return Response(
                {
                    "code": "sales_closed",
                    "detail": "La venta para este viaje cerró diez minutos después de la salida.",
                    "sales_close_at": sales_meta["sales_close_at"],
                    "server_time": sales_meta["server_time"],
                },
                status=status.HTTP_409_CONFLICT,
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
