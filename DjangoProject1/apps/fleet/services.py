import logging
from django.core.exceptions import ValidationError
from django.db import transaction

from DjangoProject1.apps.fleet.models import Bus, Seat

logger = logging.getLogger(__name__)


def canonical_seat_number(value):
    """Obtiene la clave canónica para un número de asiento.
    Si es puramente numérico (ej. '01', '001', '1'), devuelve el entero como str ('1').
    Si es alfanumérico (ej. '1A', 'P1'), lo normaliza en minúsculas sin espacios.
    """
    cleaned = str(value).strip()
    if cleaned.isdigit():
        return str(int(cleaned))
    return cleaned.lower()


def canonical_position(row, col):
    """Normaliza las coordenadas físicas (fila, columna) a una tupla canónica.
    - '01' y '1' se normalizan a '1'.
    - Columnas 'A', 'B', 'C', 'D' o '1', '2', '3', '4' se normalizan a '1', '2', '3', '4'.
    """
    r_str = str(row).strip()
    r_canon = str(int(r_str)) if r_str.isdigit() else r_str.lower()

    c_str = str(col).strip().upper()
    col_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
    if c_str in col_map:
        c_canon = col_map[c_str]
    elif c_str.isdigit():
        c_canon = str(int(c_str))
    else:
        c_canon = c_str.lower()

    return (r_canon, c_canon)


def diagnose_bus_seats(bus):
    """Analiza la consistencia física y lógica del plano de asientos de un bus sin modificar la BD.

    Detecta:
    - Duplicados numéricos canónicos (ej. '01' y '1' con diferentes IDs).
    - Colisiones de posición física (ej. dos asientos en fila 1, col 1).
    - Conteo superior a la capacidad del bus.
    - Referencias asociadas a cada asiento (Ticket, Sale, SaleItem, CurrentSeatState, SeatsStateRecord).
    """
    from DjangoProject1.apps.sales.models import Sale, SaleItem, Ticket
    from DjangoProject1.apps.trips.models import CurrentSeatState, SeatsStateRecord

    seats = list(Seat.objects.filter(bus=bus).order_by("id"))
    canonical_num_map = {}
    canonical_pos_map = {}

    numeric_duplicates = []
    position_collisions = []

    # Diagnóstico de referencias por cada asiento
    seats_detail = []
    for s in seats:
        c_num = canonical_seat_number(s.seat_number)
        c_pos = canonical_position(s.row, s.col)

        tickets_count = Ticket.objects.filter(seat=s).count()
        sales_count = Sale.objects.filter(seat=s).count()
        sale_items_count = SaleItem.objects.filter(seat=s).count()
        active_tickets_count = Ticket.objects.filter(
            seat=s, status=Ticket.Status.ISSUED
        ).count()
        current_state_count = CurrentSeatState.objects.filter(seat=s).count()
        history_state_count = SeatsStateRecord.objects.filter(seat=s).count()

        detail = {
            "id": s.id,
            "seat_number": s.seat_number,
            "canonical_number": c_num,
            "row": s.row,
            "col": s.col,
            "canonical_position": c_pos,
            "tickets_count": tickets_count,
            "active_tickets_count": active_tickets_count,
            "sales_count": sales_count,
            "sale_items_count": sale_items_count,
            "current_state_count": current_state_count,
            "history_state_count": history_state_count,
            "has_references": bool(
                tickets_count or sales_count or sale_items_count or current_state_count or history_state_count
            ),
        }
        seats_detail.append(detail)

        # Mapeo de duplicados numéricos
        canonical_num_map.setdefault(c_num, []).append(detail)
        # Mapeo de colisiones de posición
        canonical_pos_map.setdefault(c_pos, []).append(detail)

    for c_num, group in canonical_num_map.items():
        if len(group) > 1:
            numeric_duplicates.append({
                "canonical_number": c_num,
                "seats": group,
            })

    for c_pos, group in canonical_pos_map.items():
        if len(group) > 1:
            position_collisions.append({
                "canonical_position": c_pos,
                "seats": group,
            })

    is_inconsistent = bool(
        numeric_duplicates
        or position_collisions
        or (len(seats) > bus.capacity)
    )

    errors = []
    if numeric_duplicates:
        dups_desc = ", ".join(
            f"clave {d['canonical_number']}: IDs {[s['id'] for s in d['seats']]}"
            for d in numeric_duplicates
        )
        errors.append(f"Existen asientos con numeración equivalente/duplicada ({dups_desc}).")
    if position_collisions:
        pos_desc = ", ".join(
            f"posición {p['canonical_position']}: IDs {[s['id'] for s in p['seats']]}"
            for p in position_collisions
        )
        errors.append(f"Existen colisiones físicas de posición ({pos_desc}).")
    if len(seats) > bus.capacity:
        errors.append(
            f"El número de asientos ({len(seats)}) supera la capacidad del bus ({bus.capacity})."
        )

    return {
        "bus_id": bus.id,
        "bus_plate": bus.plate,
        "capacity": bus.capacity,
        "total_seats": len(seats),
        "is_inconsistent": is_inconsistent,
        "errors": errors,
        "numeric_duplicates": numeric_duplicates,
        "position_collisions": position_collisions,
        "seats_detail": seats_detail,
    }


def validate_bus_seats_integrity(bus):
    """Valida que el plano del bus sea consistente antes de realizar ventas, checkout o completado.
    Lanza ValidationError si hay duplicados numéricos, colisiones físicas o sobrecapacidad.
    """
    diagnosis = diagnose_bus_seats(bus)
    if diagnosis["is_inconsistent"]:
        raise ValidationError({
            "seats_plan_inconsistent": True,
            "bus_plate": bus.plate,
            "detail": (
                f"El bus {bus.plate} presenta inconsistencias en su plano de asientos: "
                + " ".join(diagnosis["errors"])
            ),
            "errors": diagnosis["errors"],
        })
    return diagnosis


def reconcile_bus_seats(bus, dry_run=True):
    """Concilia de forma segura duplicados en el plano de asientos.

    Reglas estrictas de conciliación:
    1. Si existen dos asientos canónicamente idénticos (ej. '01' y '1'):
       - Si uno tiene referencias (tiquetes/ventas) y el otro no tiene NINGUNA referencia,
         el que no tiene referencias se puede desvincular/eliminar de forma segura.
       - Si AMBOS tienen tiquetes activos para el mismo viaje o diferentes viajes,
         NO se fusionan a ciegas; se marca como 'requires_manual_audit'.
       - Si uno tiene referencias históricas y el otro no, se conserva el que tiene referencias.
    2. Retorna un informe detallado de las acciones simuladas o realizadas.
    """
    from DjangoProject1.apps.sales.models import Sale, SaleItem, Ticket
    from DjangoProject1.apps.trips.models import CurrentSeatState, SeatsStateRecord

    diagnosis = diagnose_bus_seats(bus)
    actions = []
    requires_manual_audit = False

    with transaction.atomic():
        for dup in diagnosis["numeric_duplicates"]:
            seats_group = dup["seats"]
            # Ordenar: preferir el que tiene referencias (especialmente tiquetes activos)
            # y en caso de empate, el ID más bajo
            referenced = [s for s in seats_group if s["has_references"]]
            unreferenced = [s for s in seats_group if not s["has_references"]]

            active_ticketed = [s for s in seats_group if s["active_tickets_count"] > 0]
            if len(active_ticketed) > 1:
                # Conflicto operativo real: dos asientos duplicados con tiquetes activos
                requires_manual_audit = True
                actions.append({
                    "canonical_number": dup["canonical_number"],
                    "status": "requires_manual_audit",
                    "reason": "Múltiples registros equivalentes tienen tiquetes activos emitidos.",
                    "seats": seats_group,
                })
                continue

            if len(referenced) <= 1 and unreferenced:
                # El asiento maestro es el referenciado (o el primero no referenciado)
                master = referenced[0] if referenced else unreferenced[0]
                to_remove = [s for s in unreferenced if s["id"] != master["id"]]

                for rem in to_remove:
                    action_detail = {
                        "canonical_number": dup["canonical_number"],
                        "status": "removed" if not dry_run else "would_remove",
                        "seat_id": rem["id"],
                        "seat_number": rem["seat_number"],
                        "retained_seat_id": master["id"],
                        "retained_seat_number": master["seat_number"],
                    }
                    if not dry_run:
                        Seat.objects.filter(id=rem["id"]).delete()
                    actions.append(action_detail)
            else:
                requires_manual_audit = True
                actions.append({
                    "canonical_number": dup["canonical_number"],
                    "status": "requires_manual_audit",
                    "reason": "Ambos registros tienen referencias asociadas.",
                    "seats": seats_group,
                })

        if dry_run:
            # En modo dry-run revertimos cualquier cambio
            transaction.set_rollback(True)

    final_diagnosis = diagnose_bus_seats(bus) if not dry_run else diagnosis
    return {
        "bus_plate": bus.plate,
        "dry_run": dry_run,
        "requires_manual_audit": requires_manual_audit,
        "actions": actions,
        "is_consistent_now": not final_diagnosis["is_inconsistent"],
        "remaining_errors": final_diagnosis["errors"],
    }


def complete_seats_for_bus(bus, target_capacity=None, columns_per_row=4):
    """Comprueba y completa los registros Seat de un bus hasta su capacidad.

    - Valida que no existan duplicados canónicos ni colisiones físicas antes de crear nada.
    - Por defecto toma la capacidad registrada en el propio bus (`bus.capacity`).
    - Usa comparación canónica para evitar duplicados entre '01' y '1'.
    - Distribución 2 + pasillo + 2 (columnas 1, 2 y 3, 4).
    - Conserva estrictamente los IDs, seat_number, row y col de los asientos existentes.
    - No elimina ni modifica asientos vinculados a tiquetes o ventas.
    """
    from DjangoProject1.apps.sales.models import Ticket

    with transaction.atomic():
        if target_capacity is None:
            target_capacity = bus.capacity
        elif bus.capacity != target_capacity:
            bus.capacity = target_capacity
            bus.save(update_fields=["capacity"])

        # 1. Validación de consistencia previa
        diagnosis = diagnose_bus_seats(bus)
        if diagnosis["is_inconsistent"]:
            raise ValidationError({
                "seats_plan_inconsistent": True,
                "bus_plate": bus.plate,
                "detail": (
                    f"No se pueden completar asientos para el bus {bus.plate} porque su plano "
                    f"presenta inconsistencias previas: " + " ".join(diagnosis["errors"])
                ),
                "errors": diagnosis["errors"],
            })

        existing_seats = list(Seat.objects.filter(bus=bus))
        # Claves numéricas canónicas de las sillas existentes (ej. '01' -> '1')
        existing_canonical_numbers = {
            canonical_seat_number(s.seat_number) for s in existing_seats
        }
        # Posiciones físicas canónicas ocupadas (ej. ('1', '1'))
        occupied_positions = {
            canonical_position(s.row, s.col) for s in existing_seats
        }

        ticketed_seat_ids = set(
            Ticket.objects.filter(seat__bus=bus).values_list("seat_id", flat=True)
        )

        created_seats = []

        # Para un bus de 2 + pasillo + 2:
        # Fila r = 1..ceil(capacity/4), Columna c = 1..4
        for num in range(1, target_capacity + 1):
            c_num = str(num)
            if c_num in existing_canonical_numbers:
                # Ya existe un asiento físicamente equivalente (sea '1', '01' o '001')
                continue

            # Posición natural en distribución 2 + pasillo + 2 (4 columnas por fila)
            nat_row = str((num - 1) // columns_per_row + 1)
            nat_col = str((num - 1) % columns_per_row + 1)
            canon_pos = canonical_position(nat_row, nat_col)

            if canon_pos in occupied_positions:
                # Si la posición física natural ya está ocupada por un asiento existente
                # con diferente número, hay una inconsistencia de plano: no inventar otra posición libre
                raise ValidationError({
                    "seats_plan_inconsistent": True,
                    "bus_plate": bus.plate,
                    "detail": (
                        f"Inconsistencia física en bus {bus.plate}: la posición {canon_pos} "
                        f"del asiento canónico {c_num} ya está ocupada en el plano."
                    ),
                })

            occupied_positions.add(canon_pos)
            created_seats.append(
                Seat(
                    bus=bus,
                    seat_number=str(num),
                    row=nat_row,
                    col=nat_col,
                )
            )

        if created_seats:
            Seat.objects.bulk_create(created_seats)
            logger.info(
                "Bus %s: creados %d asientos canónicos para completar capacidad %d.",
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
