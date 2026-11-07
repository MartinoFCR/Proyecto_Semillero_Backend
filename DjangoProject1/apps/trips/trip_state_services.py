import datetime
from django.db import models
from django.utils import timezone
from django.conf import settings


def get_server_now() -> datetime.datetime:
    """Devuelve la fecha/hora actual del servidor en la zona horaria del sistema (America/Bogota)."""
    return timezone.localtime(timezone.now())


def compute_trip_operational_state(trip, now: datetime.datetime = None) -> tuple[str, datetime.datetime]:
    """Calcula el estado operativo automático y la fecha de finalización automática estimada.
    
    Reglas:
    - scheduled: hasta 30 minutos antes de la salida (date_time_start - 30 min).
    - in_progress: desde 30 minutos antes de la salida hasta su finalización.
    - completed: al alcanzar date_time_end; si date_time_end es nulo, 4 horas después de la salida.
    
    Si el viaje tiene un estado manual terminal ('completed' o 'cancelled'), este cálculo
    informa el estado estimado sin sobreescribir la decisión manual.
    """
    if now is None:
        now = get_server_now()

    start = timezone.localtime(trip.date_time_start) if timezone.is_aware(trip.date_time_start) else timezone.make_aware(trip.date_time_start)
    
    # Finalización programada o estimada (4 horas después de la salida por defecto)
    if trip.date_time_end:
        end = timezone.localtime(trip.date_time_end) if timezone.is_aware(trip.date_time_end) else timezone.make_aware(trip.date_time_end)
    else:
        end = start + datetime.timedelta(hours=4)

    start_progress = start - datetime.timedelta(minutes=30)

    if now < start_progress:
        computed_state = "scheduled"
    elif now < end:
        computed_state = "in_progress"
    else:
        computed_state = "completed"

    return computed_state, end


def compute_trip_sales_availability(trip, now: datetime.datetime = None) -> dict:
    """Calcula la disponibilidad de venta y la metadata requerida por Angular.
    
    Reglas:
    - sales_close_at = date_time_start + 10 minutos.
    - Se permite comprar cuando:
        * Estado operativo sea 'scheduled' o 'in_progress'.
        * now < sales_close_at (no hayan pasado más de 10 min desde la salida).
        * Tenga tarifa válida (> 0).
        * Tenga capacidad disponible de sillas.
    """
    if now is None:
        now = get_server_now()

    start = timezone.localtime(trip.date_time_start) if timezone.is_aware(trip.date_time_start) else timezone.make_aware(trip.date_time_start)
    sales_close_at = start + datetime.timedelta(minutes=10)
    computed_state, auto_completion_at = compute_trip_operational_state(trip, now)

    # Estado efectivo (si fue fijado manualmente, se respeta; de lo contrario usa el automático)
    effective_state = trip.trip_state

    can_sell = True
    block_reason = None

    if effective_state == "cancelled":
        can_sell = False
        block_reason = "trip_cancelled"
    elif effective_state == "completed":
        can_sell = False
        block_reason = "trip_completed"
    elif now >= sales_close_at:
        can_sell = False
        block_reason = "sales_closed"
    elif not getattr(trip, "fare", None) or trip.fare.amount_cents <= 0:
        can_sell = False
        block_reason = "fare_missing"
    else:
        # Verificar cupo si tiene bus asignado
        if hasattr(trip, "bus") and trip.bus:
            from DjangoProject1.apps.sales.models import Ticket
            issued_count = Ticket.objects.filter(trip=trip, status=Ticket.Status.ISSUED).count()
            if issued_count >= trip.bus.capacity:
                can_sell = False
                block_reason = "sold_out"

    return {
        "id": trip.id,
        "trip_state": effective_state,
        "state_source": getattr(trip, "state_source", "automatic"),
        "date_time_start": start.isoformat(),
        "date_time_end": trip.date_time_end.isoformat() if trip.date_time_end else None,
        "automatic_completion_at": auto_completion_at.isoformat(),
        "sales_close_at": sales_close_at.isoformat(),
        "can_sell": can_sell,
        "sales_block_reason": block_reason,
        "server_time": now.isoformat(),
    }
