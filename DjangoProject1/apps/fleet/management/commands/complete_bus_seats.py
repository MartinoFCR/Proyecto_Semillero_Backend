import json
from django.core.management.base import BaseCommand, CommandError

from DjangoProject1.apps.fleet.models import Bus, Seat
from DjangoProject1.apps.fleet.services import complete_seats_for_bus


class Command(BaseCommand):
    help = (
        "Comprueba y completa los registros Seat de un bus (por defecto DEMO-002) "
        "hasta su capacidad objetivo con distribución 2 + pasillo + 2."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--plate",
            type=str,
            default="DEMO-002",
            help="Placa del bus a completar (por defecto: DEMO-002).",
        )
        parser.add_argument(
            "--capacity",
            type=int,
            default=None,
            help="Capacidad objetivo (por defecto toma la capacidad registrada en el bus).",
        )
        parser.add_argument(
            "--columns",
            type=int,
            default=4,
            help="Número de columnas por fila para 2+pasillo+2 (por defecto: 4).",
        )

    def handle(self, *args, **options):
        plate = options["plate"].strip()
        capacity = options["capacity"]
        columns = options["columns"]

        try:
            bus = Bus.objects.get(plate__iexact=plate)
        except Bus.DoesNotExist:
            raise CommandError(f"No se encontró ningún bus con la placa '{plate}'.")

        result = complete_seats_for_bus(
            bus=bus,
            target_capacity=capacity,
            columns_per_row=columns,
        )

        seats = list(
            Seat.objects.filter(bus=bus).order_by("id")
        )
        seats_by_row = {}
        for s in seats:
            seats_by_row.setdefault(s.row, []).append({
                "id": s.id,
                "seat_number": s.seat_number,
                "col": s.col,
            })

        summary = {
            **result,
            "distribution_summary": {
                f"Fila {r}": seats_by_row[r]
                for r in sorted(seats_by_row.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
            },
        }

        self.stdout.write(self.style.SUCCESS(
            f"Bus {bus.plate} verificado y completado exitosamente."
        ))
        self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False))
