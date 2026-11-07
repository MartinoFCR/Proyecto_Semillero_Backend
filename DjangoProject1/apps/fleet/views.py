
from django.db import models
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, Seat
from DjangoProject1.apps.fleet.serializers import (
    BusSerializer,
    BusTypeSerializer,
    DriverSerializer,
    SeatSerializer,
)
from DjangoProject1.apps.fleet.services import complete_seats_for_bus
from DjangoProject1.permissions import IsAdminOrReadOnly


class BusViewSet(ModelViewSet):
    queryset = Bus.objects.all().order_by("id")
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]


class BusTypeViewSet(ModelViewSet):
    queryset = BusType.objects.all()
    serializer_class = BusTypeSerializer
    permission_classes = [IsAdminOrReadOnly]


class DriverViewSet(ModelViewSet):
    queryset = Driver.objects.all().order_by("id")
    serializer_class = DriverSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        license_num = self.request.query_params.get("license_number", "").strip()
        is_active_param = self.request.query_params.get("is_active")

        if is_active_param is not None:
            val = is_active_param.strip().lower()
            if val in {"true", "1"}:
                queryset = queryset.filter(is_active=True)
            elif val in {"false", "0"}:
                queryset = queryset.filter(is_active=False)

        if license_num:
            queryset = queryset.filter(license_number__icontains=license_num)
        if search:
            queryset = queryset.filter(
                models.Q(full_name__icontains=search)
                | models.Q(license_number__icontains=search)
                | models.Q(phone_number__icontains=search)
            )
        return queryset


class SeatViewSet(ModelViewSet):
    queryset = Seat.objects.select_related("bus").all().order_by("id")
    serializer_class = SeatSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        bus_id = self.request.query_params.get("bus")
        if bus_id:
            try:
                bus = Bus.objects.get(pk=bus_id)
                if bus.seats.count() < bus.capacity:
                    complete_seats_for_bus(bus, bus.capacity)
            except (Bus.DoesNotExist, ValueError):
                pass
            queryset = queryset.filter(bus_id=bus_id)
        return queryset
