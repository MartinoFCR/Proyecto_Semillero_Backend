
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, Seat
from DjangoProject1.apps.fleet.serializers import (
    BusSerializer,
    BusTypeSerializer,
    DriverSerializer,
    SeatSerializer,
)
from DjangoProject1.apps.fleet.services import complete_seats_for_bus
from DjangoProject1.permissions import IsAdminOrReadOnly, IsAdminOrOwnDriver


class BusViewSet(ModelViewSet):
    queryset = Bus.objects.all().order_by("id")
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]


class BusTypeViewSet(ModelViewSet):
    queryset = BusType.objects.all()
    serializer_class = BusTypeSerializer
    permission_classes = [IsAdminOrReadOnly]


class DriverViewSet(ModelViewSet):
    queryset = Driver.objects.select_related("user").all()
    serializer_class = DriverSerializer
    permission_classes = [IsAdminOrOwnDriver]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == "admin":
            return queryset
        return queryset.filter(user=self.request.user)


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
