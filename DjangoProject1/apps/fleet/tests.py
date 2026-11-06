from django.core.management import call_command
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from DjangoProject1.apps.fleet.models import Bus, BusType, Seat
from DjangoProject1.apps.fleet.serializers import BusSerializer
from DjangoProject1.apps.fleet.services import complete_seats_for_bus


class BusTypeTests(TestCase):
    def setUp(self):
        self.bus_type = BusType.objects.create(
            name="Bus urbano",
            code="bus-urbano",
            max_capacity=60,
        )

    def test_bus_capacity_cannot_exceed_type_capacity(self):
        serializer = BusSerializer(data={
            "plate": "ABC123",
            "capacity": 61,
            "model": "2024",
            "bus_type": self.bus_type.id,
            "state": Bus.State.ACTIVE,
        })

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_bus_type_is_optional_for_existing_bus_compatibility(self):
        bus = Bus.objects.create(
            plate="DEF456",
            capacity=40,
            model="2024",
        )

        self.assertIsNone(bus.bus_type)


class DemoBusSeatCompletionTests(TestCase):
    def setUp(self):
        self.bus = Bus.objects.create(
            plate="DEMO-002",
            capacity=30,
            model="Mercedes-Benz 2024",
            state=Bus.State.ACTIVE,
        )
        # Simular los 10 asientos existentes iniciales
        self.initial_seats = []
        for i in range(1, 11):
            row = str((i - 1) // 4 + 1)
            col = str((i - 1) % 4 + 1)
            seat = Seat.objects.create(
                bus=self.bus,
                seat_number=str(i),
                row=row,
                col=col,
            )
            self.initial_seats.append(seat)

    def test_complete_seats_preserves_existing_ids_and_completes_to_30(self):
        initial_ids = {s.id for s in self.initial_seats}
        initial_positions = {(s.seat_number, s.row, s.col) for s in self.initial_seats}

        result = complete_seats_for_bus(self.bus, target_capacity=30)

        self.assertEqual(result["existing_seats_count"], 10)
        self.assertEqual(result["created_seats_count"], 20)
        self.assertEqual(result["total_seats_count"], 30)

        all_seats = list(Seat.objects.filter(bus=self.bus))
        self.assertEqual(len(all_seats), 30)

        # Verificar que los IDs y posiciones existentes se conservaron intactos
        current_ids = {s.id for s in all_seats}
        self.assertTrue(initial_ids.issubset(current_ids))

        for seat in all_seats:
            if seat.id in initial_ids:
                self.assertIn((seat.seat_number, seat.row, seat.col), initial_positions)

        # Verificar números del 1 al 30 sin duplicados
        seat_numbers = {s.seat_number for s in all_seats}
        expected_numbers = {str(n) for n in range(1, 31)}
        self.assertEqual(seat_numbers, expected_numbers)

        # Verificar distribución 2 + pasillo + 2 (columnas 1..4)
        for seat in all_seats:
            self.assertIn(seat.col, {"1", "2", "3", "4"})
            row_int = int(seat.row)
            self.assertGreaterEqual(row_int, 1)
            self.assertLessEqual(row_int, 8)

        # Filas 1 a 7 deben tener 4 asientos (2 + pasillo + 2)
        rows = {}
        for s in all_seats:
            rows.setdefault(s.row, set()).add(s.col)

        for r in range(1, 8):
            self.assertEqual(rows[str(r)], {"1", "2", "3", "4"}, f"Fila {r} incompleta")

        # Fila 8 completa los 30 asientos (2 asientos)
        self.assertEqual(len(rows["8"]), 2)

    def test_complete_seats_is_idempotent(self):
        complete_seats_for_bus(self.bus, target_capacity=30)
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 30)

        # Ejecución repetida no debe crear duplicados
        result = complete_seats_for_bus(self.bus, target_capacity=30)
        self.assertEqual(result["created_seats_count"], 0)
        self.assertEqual(result["total_seats_count"], 30)
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 30)

    def test_management_command_completes_demo002_bus(self):
        out = call_command("complete_bus_seats", plate="DEMO-002")
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 30)
