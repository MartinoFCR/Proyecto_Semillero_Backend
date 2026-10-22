
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.utils import timezone
from DjangoProject1.apps.sales.models import Sale, Ticket

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
    permission_classes = [IsAdminOrAssignedDriverReadOnly]

    def get_permissions(self):
        if self.request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            return [IsAdminRole()]
        if getattr(self.request.user, "role", None) == "client":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Trip.objects.select_related(
            "bus",
            "driver",
            "driver__user",
            "route",
            "route__origin",
            "route__destination",
        )

        if self.request.user.role == "admin":
            return queryset.all()

        if self.request.user.role == "client":
            return queryset.filter(
                trip_state=Trip.TripState.SCHEDULED,
            )

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(driver=driver_profile)


class TripFareViewSet(ModelViewSet):
    queryset = TripFare.objects.select_related("trip").all()
    serializer_class = TripFareSerializer
    permission_classes = [IsAdminOrReadOnly]


class AvailableSeatsView(APIView):
    permission_classes = [IsAuthenticated]

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
        now = timezone.now()
        expired_holds = Sale.objects.filter(
            trip=trip,
            source=Sale.Source.ONLINE,
            status=Sale.Status.PENDING,
            expires_at__lte=now,
        )
        expired_holds.update(
            status=Sale.Status.EXPIRED,
            updated_at=now,
        )

        seats = []
        for seat in trip.bus.seats.all().order_by("seat_number"):
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
