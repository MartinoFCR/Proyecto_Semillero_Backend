
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from DjangoProject1.apps.trips.models import (
    Trip,
    Reading,
    Event,
    CurrentSeatState,
    SeatsStateRecord,
)
from DjangoProject1.apps.trips.serializers import (
    TripSerializer,
    ReadingSerializer,
    EventSerializer,
    CurrentSeatStateSerializer,
    SeatsStateRecordSerializer,
)
from DjangoProject1.permissions import (
    IsAdminRole,
    IsAdminOrAssignedDriverReadOnly,
    IsAdminOrAssignedDriver,
)


class TripViewSet(ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsAdminOrAssignedDriverReadOnly]

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

        driver_profile = getattr(
            self.request.user,
            "driver_profile",
            None,
        )

        if driver_profile is None:
            return queryset.none()

        return queryset.filter(driver=driver_profile)


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
