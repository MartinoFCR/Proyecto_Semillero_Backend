import logging
from django.db import transaction

from DjangoProject1.apps.fleet.models import Bus, Seat

logger = logging.getLogger(__name__)


def complete_seats_for_bus(bus, target_capacity=None, columns_per_row=4):
    """Comprueba y completa los registros Seat de un bus hasta su capacidad.

    - Por defecto toma la capacidad registrada en el propio bus (`bus.capacity`).
    - Distribución 2 + pasillo + 2 (columnas 1, 2 y 3, 4).
    - Conserva estrictamente los IDs, seat_number, row y col de los asientos existentes.
    - No elimina ni modifica asientos vinculados a tiquetes o ventas.
    - Asigna números de silla del 1 a la capacidad del bus.
    """
    from DjangoProject1.apps.sales.models import Ticket

    with transaction.atomic():
        if target_capacity is None:
            target_capacity = bus.capacity
        elif bus.capacity != target_capacity:
            bus.capacity = target_capacity
            bus.save(update_fields=["capacity"])

        existing_seats = list(Seat.objects.filter(bus=bus))
        existing_numbers = {str(s.seat_number) for s in existing_seats}
        occupied_positions = {
            (str(s.row), str(s.col)) for s in existing_seats
        }

        # Verificar asientos con tiquetes para garantizar que queden intactos
        ticketed_seat_ids = set(
            Ticket.objects.filter(seat__bus=bus).values_list("seat_id", flat=True)
        )

        created_seats = []

        def get_free_position():
            r = 1
            while True:
                for c in range(1, columns_per_row + 1):
                    pos = (str(r), str(c))
                    if pos not in occupied_positions:
                        return pos
                r += 1

        for num in range(1, target_capacity + 1):
            num_str = str(num)
            if num_str in existing_numbers:
                # El asiento ya existe, se respeta id y posición original
                continue

            # Posición natural en distribución 2 + pasillo + 2 (4 columnas por fila)
            nat_row = str((num - 1) // columns_per_row + 1)
            nat_col = str((num - 1) % columns_per_row + 1)

            if (nat_row, nat_col) not in occupied_positions:
                chosen_row, chosen_col = nat_row, nat_col
            else:
                chosen_row, chosen_col = get_free_position()

            occupied_positions.add((chosen_row, chosen_col))
            created_seats.append(
                Seat(
                    bus=bus,
                    seat_number=num_str,
                    row=chosen_row,
                    col=chosen_col,
                )
            )

        if created_seats:
            Seat.objects.bulk_create(created_seats)
            logger.info(
                "Bus %s: creados %d asientos para completar capacidad %d.",
                bus.plate,
                len(created_seats),
                target_capacity,
            )

        final_seats = list(Seat.objects.filter(bus=bus))

        return {
            "bus_plate": bus.plate,
            "capacity": bus.capacity,
            "existing_seats_count": len(existing_seats),
            "created_seats_count": len(created_seats),
            "total_seats_count": len(final_seats),
            "ticketed_seats_count": len(ticketed_seat_ids),
            "created_seat_numbers": [s.seat_number for s in created_seats],
        }
