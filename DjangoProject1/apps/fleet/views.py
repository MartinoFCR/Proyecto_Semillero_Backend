
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, Seat
from DjangoProject1.apps.fleet.serializers import (
    BusSerializer,
    BusTypeSerializer,
    DriverSerializer,
    SeatSerializer,
)
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
    queryset = Driver.objects.select_related("user").all()
    serializer_class = DriverSerializer
    permission_classes = [IsAdminOrReadOnly]


class SeatViewSet(ModelViewSet):
    queryset = Seat.objects.select_related("bus").all()
    serializer_class = SeatSerializer
    permission_classes = [IsAdminOrReadOnly]
