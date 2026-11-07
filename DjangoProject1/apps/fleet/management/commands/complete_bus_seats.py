import json
from django.core.management.base import BaseCommand, CommandError

from DjangoProject1.apps.fleet.models import Bus
from DjangoProject1.apps.fleet.services import (
    complete_seats_for_bus,
    diagnose_bus_seats,
    reconcile_bus_seats,
)


class Command(BaseCommand):
    help = (
        "Diagnostica, concilia duplicados y completa los registros Seat de un bus "
        "con validación canónica estricta y auditoría de boletas existentes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--plate",
            type=str,
            default=None,
            help="Placa del bus.",
        )
        parser.add_argument(
            "--all-buses",
            action="store_true",
            help="Ejecuta la acción sobre todos los buses registrados.",
        )
        parser.add_argument(
            "--diagnose-only",
            action="store_true",
            help="Solo ejecuta el diagnóstico sin modificar datos ni completar sillas.",
        )
        parser.add_argument(
            "--reconcile",
            action="store_true",
            help="Ejecuta la conciliación de duplicados (por defecto en modo simulación dry-run).",
        )
        parser.add_argument(
            "--apply-reconciliation",
            action="store_true",
            help="Aplica los cambios de conciliación de duplicados en la base de datos.",
        )
        parser.add_argument(
            "--capacity",
            type=int,
            default=None,
            help="Capacidad objetivo (por defecto toma la capacidad registrada en el bus).",
        )

    def handle(self, *args, **options):
        plate = options["plate"].strip() if options["plate"] else None
        all_buses = options["all_buses"]
        diagnose_only = options["diagnose_only"]
        reconcile = options["reconcile"]
        apply_reconciliation = options["apply_reconciliation"]
        capacity = options["capacity"]

        if not plate and not all_buses:
            plate = "DEMO-002"

        if all_buses:
            buses = list(Bus.objects.all().order_by("id"))
        else:
            try:
                # Permitir buscar por placa o por ID numérico de bus
                if plate.isdigit():
                    bus = Bus.objects.get(id=int(plate))
                else:
                    bus = Bus.objects.get(plate__iexact=plate)
                buses = [bus]
            except Bus.DoesNotExist:
                raise CommandError(f"No se encontró ningún bus con la placa o ID '{plate}'.")

        for bus in buses:
            self._process_bus(
                bus=bus,
                diagnose_only=diagnose_only,
                reconcile=reconcile,
                apply_reconciliation=apply_reconciliation,
                capacity=capacity,
            )

    def _process_bus(self, bus, diagnose_only, reconcile, apply_reconciliation, capacity):
        # 1. Diagnóstico
        diagnosis = diagnose_bus_seats(bus)
        self.stdout.write(self.style.NOTICE(f"\n=== Diagnóstico del bus {bus.plate} (ID {bus.id}) ==="))
        self.stdout.write(f"Capacidad: {bus.capacity} | Asientos actuales: {diagnosis['total_seats']}")
        self.stdout.write(f"Consistencia del plano: {'CORRECTA' if not diagnosis['is_inconsistent'] else 'INCONSISTENTE'}")

        if diagnosis["errors"]:
            for err in diagnosis["errors"]:
                self.stdout.write(self.style.ERROR(f" - {err}"))

        if diagnose_only:
            self.stdout.write(json.dumps(diagnosis, indent=2, ensure_ascii=False))
            return

        # 2. Conciliación si se solicita
        if reconcile or apply_reconciliation:
            dry_run = not apply_reconciliation
            self.stdout.write(self.style.NOTICE(
                f"\n=== Ejecutando conciliación ({'DRY-RUN (Simulación)' if dry_run else 'APLICANDO CAMBIOS'}) ==="
            ))
            reconciliation_result = reconcile_bus_seats(bus, dry_run=dry_run)
            self.stdout.write(json.dumps(reconciliation_result, indent=2, ensure_ascii=False))

            if reconciliation_result["requires_manual_audit"]:
                self.stdout.write(self.style.WARNING(
                    "ADVERTENCIA: Hay asientos duplicados con boletas/referencias activas. "
                    "Se requiere auditoría manual antes de completar el plano."
                ))
                return

            if not reconciliation_result["is_consistent_now"] and not dry_run:
                self.stdout.write(self.style.ERROR(
                    "No se pudo completar el bus porque aún persisten inconsistencias."
                ))
                return

        # 3. Completar asientos si el plano es consistente
        try:
            result = complete_seats_for_bus(bus, target_capacity=capacity)
            self.stdout.write(self.style.SUCCESS(
                f"Bus {bus.plate} completado exitosamente: "
                f"Capacidad {result['capacity']}, "
                f"Existentes {result['existing_seats_count']}, "
                f"Nuevos creados {result['created_seats_count']}, "
                f"Total {result['total_seats_count']}."
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error al completar asientos: {exc}"))
