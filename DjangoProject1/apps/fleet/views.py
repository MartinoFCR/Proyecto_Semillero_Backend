import secrets
from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from DjangoProject1.apps.fleet.models import Bus, BusType, Driver, GPSDevice, Seat
from DjangoProject1.apps.fleet.serializers import (
    BusSerializer,
    BusTypeSerializer,
    DriverSerializer,
    GPSDeviceSerializer,
    SeatSerializer,
)
from DjangoProject1.apps.fleet.services import complete_seats_for_bus
from DjangoProject1.permissions import IsAdminOrReadOnly


class BusViewSet(ModelViewSet):
    queryset = Bus.objects.select_related("bus_type", "gps_device").all().order_by("id")
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        has_gps = self.request.query_params.get("has_gps")
        if has_gps is not None:
            val = has_gps.strip().lower()
            if val in {"true", "1"}:
                queryset = queryset.filter(gps_device__isnull=False)
            elif val in {"false", "0"}:
                queryset = queryset.filter(gps_device__isnull=True)
        return queryset

    @action(detail=True, methods=["post"], url_path="assign-device")
    def assign_device(self, request, pk=None):
        bus = self.get_object()
        device_id = request.data.get("device_id")
        if not device_id:
            return Response(
                {"device_id": "Este campo es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            device = GPSDevice.objects.get(pk=device_id)
        except GPSDevice.DoesNotExist:
            return Response(
                {"detail": f"No se encontró el dispositivo con ID {device_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(bus, "gps_device") and bus.gps_device:
            old_device = bus.gps_device
            old_device.bus = None
            old_device.save(update_fields=["bus"])

        device.bus = bus
        device.save(update_fields=["bus"])
        return Response(
            {
                "detail": f"Dispositivo '{device.name}' asignado exitosamente al bus '{bus.plate}'.",
                "bus": BusSerializer(bus).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-device")
    def remove_device(self, request, pk=None):
        bus = self.get_object()
        if not hasattr(bus, "gps_device") or not bus.gps_device:
            return Response(
                {"detail": f"El bus '{bus.plate}' no tiene ningún dispositivo asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = bus.gps_device
        device.bus = None
        device.save(update_fields=["bus"])
        return Response(
            {
                "detail": f"Dispositivo '{device.name}' desvinculado del bus '{bus.plate}'.",
                "bus": BusSerializer(bus).data,
            },
            status=status.HTTP_200_OK,
        )


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


class GPSDeviceViewSet(ModelViewSet):
    queryset = GPSDevice.objects.select_related("bus").all().order_by("id")
    serializer_class = GPSDeviceSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        available = self.request.query_params.get("available")
        state_param = self.request.query_params.get("state")
        search = self.request.query_params.get("search", "").strip()

        if available is not None:
            val = available.strip().lower()
            if val in {"true", "1"}:
                queryset = queryset.filter(bus__isnull=True)
            elif val in {"false", "0"}:
                queryset = queryset.filter(bus__isnull=False)

        if state_param:
            queryset = queryset.filter(state=state_param)

        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search)
                | models.Q(device_id__icontains=search)
                | models.Q(model__icontains=search)
                | models.Q(bus__plate__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        # Generar clave segura única estilo token (ej. esp_live_32caracteres)
        raw_key = f"esp_live_{secrets.token_urlsafe(24)}"
        device = serializer.save()
        device.set_api_key(raw_key)
        device.save(update_fields=["api_key_hash", "api_key_prefix"])
        # Inyectar temporalmente en el serializer para retornarla únicamente en la respuesta de creación
        device.raw_api_key = raw_key
        serializer.instance = device

    @action(detail=True, methods=["post"], url_path="regenerate-key")
    def regenerate_key(self, request, pk=None):
        """Regenera la clave de seguridad del dispositivo. La clave anterior queda invalidada."""
        device = self.get_object()
        raw_key = f"esp_live_{secrets.token_urlsafe(24)}"
        device.set_api_key(raw_key)
        device.save(update_fields=["api_key_hash", "api_key_prefix"])

        data = GPSDeviceSerializer(device).data
        data["raw_api_key"] = raw_key
        return Response(
            {
                "detail": "Clave del dispositivo regenerada exitosamente. Guarda esta clave ahora, no volverá a mostrarse.",
                "device": data,
                "api_key": raw_key,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign_to_bus(self, request, pk=None):
        device = self.get_object()
        bus_id = request.data.get("bus")
        if not bus_id:
            return Response(
                {"bus": "El identificador del bus es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            bus = Bus.objects.get(pk=bus_id)
        except Bus.DoesNotExist:
            return Response(
                {"detail": f"No se encontró el bus con ID {bus_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(bus, "gps_device") and bus.gps_device and bus.gps_device.pk != device.pk:
            old = bus.gps_device
            old.bus = None
            old.save(update_fields=["bus"])

        device.bus = bus
        device.save(update_fields=["bus"])
        return Response(
            {
                "detail": f"Dispositivo '{device.name}' asignado exitosamente al bus '{bus.plate}'.",
                "device": GPSDeviceSerializer(device).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unassign")
    def unassign_from_bus(self, request, pk=None):
        device = self.get_object()
        if not device.bus:
            return Response(
                {"detail": "El dispositivo no está asignado a ningún bus."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_plate = device.bus.plate
        device.bus = None
        device.save(update_fields=["bus"])
        return Response(
            {
                "detail": f"Dispositivo '{device.name}' desvinculado del bus '{old_plate}'.",
                "device": GPSDeviceSerializer(device).data,
            },
            status=status.HTTP_200_OK,
        )


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
