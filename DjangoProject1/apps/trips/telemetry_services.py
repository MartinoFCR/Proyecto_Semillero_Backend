import logging
from decimal import Decimal
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from DjangoProject1.apps.fleet.models import GPSDevice, Seat
from DjangoProject1.apps.fleet.services import canonical_seat_number
from DjangoProject1.apps.trips.models import CurrentSeatState, Reading, SeatsStateRecord, Trip

logger = logging.getLogger(__name__)


def ingest_device_telemetry(payload: dict) -> dict:
    """Procesa e ingesta la telemetría enviada por un dispositivo ESP32 / IoT.

    Estructura esperada en el payload:
    {
        "device_id": "ESP32_BUS_001",
        "timestamp": "2026-11-06T21:45:00Z",  (opcional, por defecto now())
        "gps": {
            "lat": 6.2442,
            "lng": -75.5812,
            "speed": 55.0,                    (opcional)
            "fuel_level": 75.5                (opcional)
        },
        "seats": [                            (opcional)
            {"seat": "1", "occupied": true},
            {"seat": "2", "occupied": false}
        ]
    }

    Comportamiento:
    1. Valida existencia y estado activo del dispositivo.
    2. Actualiza last_ping_at en el dispositivo.
    3. Si el dispositivo tiene un bus asignado y ese bus tiene un viaje en curso
       ('in_progress' o 'scheduled'):
       - Registra una lectura en Reading con ubicación, velocidad y combustible.
       - Actualiza CurrentSeatState y agrega registro a SeatsStateRecord si hubo cambio de estado.
    """
    device_id = payload.get("device_id")
    if not device_id:
        raise ValidationError({"device_id": "El identificador del dispositivo (device_id) es obligatorio."})

    try:
        device = GPSDevice.objects.select_related("bus").get(device_id__iexact=device_id.strip())
    except GPSDevice.DoesNotExist:
        raise ValidationError({"device_id": f"No se encontró ningún dispositivo registrado con device_id '{device_id}'."})

    if device.state != GPSDevice.State.ACTIVE:
        raise ValidationError({"device_id": f"El dispositivo '{device.name}' se encuentra en estado '{device.state}' y no puede reportar datos."})

    # Timestamp de la lectura (respeta el reloj satelital del ESP32 si viene informado)
    time_stamp = timezone.now()
    raw_timestamp = payload.get("timestamp")
    if raw_timestamp:
        parsed = parse_datetime(raw_timestamp)
        if parsed:
            time_stamp = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)

    device.last_ping_at = time_stamp
    device.save(update_fields=["last_ping_at"])

    bus = device.bus
    if not bus:
        return {
            "device_id": device.device_id,
            "device_name": device.name,
            "status": "ping_received_unassigned",
            "detail": "Lectura registrada pero el dispositivo no está asignado a ningún bus.",
            "timestamp": time_stamp.isoformat(),
        }

    # Buscar viaje activo para el bus
    active_trip = Trip.objects.filter(
        bus=bus,
        trip_state__in=[Trip.TripState.IN_PROGRESS, Trip.TripState.SCHEDULED],
    ).order_by("-date_time_start").first()

    readings_created = 0
    seats_updated = 0

    with transaction.atomic():
        # Procesar datos GPS
        gps_data = payload.get("gps")
        if gps_data and active_trip:
            lat = gps_data.get("lat")
            lng = gps_data.get("lng")
            if lat is not None and lng is not None:
                speed = Decimal(str(gps_data.get("speed", 0.0)))
                fuel_level = Decimal(str(gps_data.get("fuel_level", 0.0)))
                point = Point(float(lng), float(lat), srid=4326)

                Reading.objects.create(
                    trip=active_trip,
                    time_stamp=time_stamp,
                    speed=speed,
                    fuel_level=fuel_level,
                    reading_point=point,
                )
                readings_created += 1

        # Procesar sensores de sillas
        seats_data = payload.get("seats")
        if seats_data and isinstance(seats_data, list) and active_trip:
            # Obtener mapa canónico de sillas del bus
            bus_seats = {
                canonical_seat_number(s.seat_number): s
                for s in Seat.objects.filter(bus=bus)
            }

            for item in seats_data:
                seat_num_raw = item.get("seat")
                is_occupied = bool(item.get("occupied", False))
                if seat_num_raw is None:
                    continue

                canon_key = canonical_seat_number(seat_num_raw)
                seat_obj = bus_seats.get(canon_key)
                if not seat_obj:
                    continue

                # Actualizar o crear estado actual
                current_state, created = CurrentSeatState.objects.get_or_create(
                    trip=active_trip,
                    seat=seat_obj,
                    defaults={
                        "occupied": is_occupied,
                        "time_stamp": time_stamp,
                    },
                )

                state_changed = created or (current_state.occupied != is_occupied)

                if not created and state_changed:
                    current_state.occupied = is_occupied
                    current_state.time_stamp = time_stamp
                    current_state.save(update_fields=["occupied", "time_stamp"])

                # Guardar en histórico solo si hubo un cambio de estado
                if state_changed:
                    SeatsStateRecord.objects.create(
                        trip=active_trip,
                        seat=seat_obj,
                        occupied=is_occupied,
                        time_stamp=time_stamp,
                    )
                    seats_updated += 1

    return {
        "device_id": device.device_id,
        "device_name": device.name,
        "bus_plate": bus.plate,
        "active_trip_id": active_trip.id if active_trip else None,
        "status": "processed",
        "readings_created": readings_created,
        "seats_updated": seats_updated,
        "timestamp": time_stamp.isoformat(),
    }
