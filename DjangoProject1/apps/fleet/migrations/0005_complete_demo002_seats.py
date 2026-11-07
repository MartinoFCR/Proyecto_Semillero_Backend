from django.db import migrations


def canonical_seat_number(value):
    cleaned = str(value).strip()
    if cleaned.isdigit():
        return str(int(cleaned))
    return cleaned.lower()


def canonical_position(row, col):
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


def complete_demo002_seats(apps, schema_editor):
    Bus = apps.get_model("fleet", "Bus")
    Seat = apps.get_model("fleet", "Seat")

    bus = Bus.objects.filter(plate__iexact="DEMO-002").first()
    if not bus:
        return

    target_capacity = bus.capacity or 30
    columns_per_row = 4

    existing_seats = list(Seat.objects.filter(bus=bus))
    existing_canonical_numbers = {
        canonical_seat_number(s.seat_number) for s in existing_seats
    }
    occupied_positions = {
        canonical_position(s.row, s.col) for s in existing_seats
    }

    # Si hay duplicados canónicos existentes, no creamos más para evitar inflar la base
    if len(existing_canonical_numbers) != len(existing_seats):
        return

    created_seats = []
    for num in range(1, target_capacity + 1):
        c_num = str(num)
        if c_num in existing_canonical_numbers:
            continue

        nat_row = str((num - 1) // columns_per_row + 1)
        nat_col = str((num - 1) % columns_per_row + 1)
        canon_pos = canonical_position(nat_row, nat_col)

        if canon_pos in occupied_positions:
            # Colisión física: detener para no corromper el plano
            return

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


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0004_bustype_bus_bus_type"),
    ]

    operations = [
        migrations.RunPython(
            complete_demo002_seats,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
