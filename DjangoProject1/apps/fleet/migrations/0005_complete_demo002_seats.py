from django.db import migrations


def complete_demo002_seats(apps, schema_editor):
    Bus = apps.get_model("fleet", "Bus")
    Seat = apps.get_model("fleet", "Seat")

    bus = Bus.objects.filter(plate__iexact="DEMO-002").first()
    if not bus:
        return

    target_capacity = bus.capacity
    columns_per_row = 4

    existing_seats = list(Seat.objects.filter(bus=bus))
    existing_numbers = {str(s.seat_number) for s in existing_seats}
    occupied_positions = {(str(s.row), str(s.col)) for s in existing_seats}

    def get_free_position():
        r = 1
        while True:
            for c in range(1, columns_per_row + 1):
                pos = (str(r), str(c))
                if pos not in occupied_positions:
                    return pos
            r += 1

    created_seats = []
    for num in range(1, target_capacity + 1):
        num_str = str(num)
        if num_str in existing_numbers:
            continue

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
