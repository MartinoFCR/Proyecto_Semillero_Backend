from django.core.management.base import BaseCommand
import datetime
import logging
from django.db import transaction
from django.utils import timezone

from DjangoProject1.apps.trips.models import Trip
from DjangoProject1.apps.trips.trip_state_services import (
    get_server_now,
    compute_trip_operational_state,
)

logger = logging.getLogger(__name__)


def synchronize_trips_operational_states(now: datetime.datetime = None) -> dict:
    """Actualiza en base de datos el estado de los viajes de forma idempotente y automática."""
    if now is None:
        now = get_server_now()

    updated_to_in_progress = 0
    updated_to_completed = 0

    candidate_trips = Trip.objects.filter(
        state_source="automatic",
        trip_state__in=[Trip.TripState.SCHEDULED, Trip.TripState.IN_PROGRESS],
    )

    with transaction.atomic():
        for trip in candidate_trips.select_for_update():
            computed_state, _ = compute_trip_operational_state(trip, now)
            if computed_state != trip.trip_state:
                old_state = trip.trip_state
                trip.trip_state = computed_state
                trip.save(update_fields=["trip_state"])
                if computed_state == Trip.TripState.IN_PROGRESS:
                    updated_to_in_progress += 1
                elif computed_state == Trip.TripState.COMPLETED:
                    updated_to_completed += 1
                logger.info(f"Viaje #{trip.id} actualizado automáticamente: {old_state} -> {computed_state}")

    return {
        "server_time": now.isoformat(),
        "updated_to_in_progress": updated_to_in_progress,
        "updated_to_completed": updated_to_completed,
    }


class Command(BaseCommand):
    help = "Sincroniza los estados operativos automáticos de los viajes según la hora del servidor (America/Bogota)."

    def handle(self, *args, **options):
        res = synchronize_trips_operational_states()
        self.stdout.write(self.style.SUCCESS(
            f"Sincronización completada ({res['server_time']}): "
            f"{res['updated_to_in_progress']} a 'in_progress', "
            f"{res['updated_to_completed']} a 'completed'."
        ))

