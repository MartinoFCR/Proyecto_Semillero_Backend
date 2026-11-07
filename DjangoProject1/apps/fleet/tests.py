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


class SeatPlanCanonicalAndReconciliationTests(TestCase):
    def setUp(self):
        self.bus = Bus.objects.create(
            plate="BUS-CANON-01",
            capacity=40,
            model="Scania 2024",
            state=Bus.State.ACTIVE,
        )

    def test_canonical_number_matching_with_leading_zeros_capacity_40(self):
        # Bus con 40 plazas y asientos iniciales '01' a '10'
        for i in range(1, 11):
            row = str((i - 1) // 4 + 1)
            col = str((i - 1) % 4 + 1)
            Seat.objects.create(
                bus=self.bus,
                seat_number=f"{i:02d}",  # '01', '02', ..., '10'
                row=row,
                col=col,
            )

        initial_seats = list(Seat.objects.filter(bus=self.bus))
        initial_ids = {s.id for s in initial_seats}
        self.assertEqual(len(initial_seats), 10)

        # Completar capacidad a 40: debe crear exactamente 30 asientos y totalizar 40
        result = complete_seats_for_bus(self.bus, target_capacity=40)
        self.assertEqual(result["existing_seats_count"], 10)
        self.assertEqual(result["created_seats_count"], 30)
        self.assertEqual(result["total_seats_count"], 40)

        all_seats = list(Seat.objects.filter(bus=self.bus))
        self.assertEqual(len(all_seats), 40)
        # Los IDs iniciales ('01'..'10') se conservaron intactos
        current_ids = {s.id for s in all_seats}
        self.assertTrue(initial_ids.issubset(current_ids))

        # Verificar que se crearon '11' a '40'
        created_numbers = set(result["created_seat_numbers"])
        expected_created = {str(n) for n in range(11, 41)}
        self.assertEqual(created_numbers, expected_created)

    def test_canonical_number_matching_with_leading_zeros_capacity_30(self):
        # Mismo caso pero con capacidad 30: debe crear solo 20 y obtener 30
        self.bus.capacity = 30
        self.bus.save()

        for i in range(1, 11):
            row = str((i - 1) // 4 + 1)
            col = str((i - 1) % 4 + 1)
            Seat.objects.create(
                bus=self.bus,
                seat_number=f"{i:02d}",
                row=row,
                col=col,
            )

        result = complete_seats_for_bus(self.bus, target_capacity=30)
        self.assertEqual(result["existing_seats_count"], 10)
        self.assertEqual(result["created_seats_count"], 20)
        self.assertEqual(result["total_seats_count"], 30)
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 30)

    def test_inconsistent_plan_with_01_and_1_blocks_completion_and_diagnoses_error(self):
        # Crear '01' y '1' con diferentes IDs en el mismo bus
        seat_01 = Seat.objects.create(bus=self.bus, seat_number="01", row="1", col="1")
        seat_1 = Seat.objects.create(bus=self.bus, seat_number="1", row="1", col="2")

        from DjangoProject1.apps.fleet.services import diagnose_bus_seats, validate_bus_seats_integrity
        diag = diagnose_bus_seats(self.bus)
        self.assertTrue(diag["is_inconsistent"])
        self.assertEqual(len(diag["numeric_duplicates"]), 1)
        self.assertEqual(diag["numeric_duplicates"][0]["canonical_number"], "1")

        # validate_bus_seats_integrity debe lanzar ValidationError
        with self.assertRaises(ValidationError):
            validate_bus_seats_integrity(self.bus)

        # complete_seats_for_bus debe rechazar la operación
        with self.assertRaises(ValidationError):
            complete_seats_for_bus(self.bus, target_capacity=40)

    def test_reconciliation_safe_cleanup_unreferenced_duplicate(self):
        # Crear '01' (con tiquete simulado) y '1' (sin tiquete)
        seat_01 = Seat.objects.create(bus=self.bus, seat_number="01", row="1", col="1")
        seat_1 = Seat.objects.create(bus=self.bus, seat_number="1", row="1", col="2")

        # Simular tiquete vinculado a seat_01
        from DjangoProject1.apps.trips.models import Route, Trip, Stop
        from DjangoProject1.apps.sales.models import Sale, Ticket
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        user = get_user_model().objects.create(username="testaudituser")
        route = Route.objects.create(name="Ruta Test", base_price=50000)
        origin = Stop.objects.create(route=route, name="Origen", order=1)
        dest = Stop.objects.create(route=route, name="Destino", order=2)
        trip = Trip.objects.create(
            bus=self.bus,
            route=route,
            origin=origin,
            destination=dest,
            departure_time=timezone.now(),
            arrival_time=timezone.now() + timezone.timedelta(hours=2),
            price=50000,
        )
        sale = Sale.objects.create(
            user=user,
            trip=trip,
            seat=seat_01,
            amount=50000,
            status=Sale.Status.PAID,
        )
        ticket = Ticket.objects.create(
            sale=sale,
            trip=trip,
            seat=seat_01,
            ticket_number="TK-TEST-001",
            status=Ticket.Status.ISSUED,
        )

        from DjangoProject1.apps.fleet.services import reconcile_bus_seats
        # Dry-run no debe eliminar nada
        dry_res = reconcile_bus_seats(self.bus, dry_run=True)
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 2)

        # Ejecución real: elimina el asiento duplicado sin tiquetes (seat_1) y preserva seat_01
        res = reconcile_bus_seats(self.bus, dry_run=False)
        self.assertFalse(res["dry_run"])
        self.assertFalse(res["requires_manual_audit"])
        self.assertTrue(res["is_consistent_now"])

        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 1)
        remaining = Seat.objects.get(bus=self.bus)
        self.assertEqual(remaining.id, seat_01.id)
        self.assertEqual(remaining.seat_number, "01")

    def test_reconciliation_requires_manual_audit_if_both_have_active_tickets(self):
        seat_01 = Seat.objects.create(bus=self.bus, seat_number="01", row="1", col="1")
        seat_1 = Seat.objects.create(bus=self.bus, seat_number="1", row="1", col="2")

        from DjangoProject1.apps.trips.models import Route, Trip, Stop
        from DjangoProject1.apps.sales.models import Sale, Ticket
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        user = get_user_model().objects.create(username="testaudituser2")
        route = Route.objects.create(name="Ruta Test 2", base_price=50000)
        origin = Stop.objects.create(route=route, name="Origen 2", order=1)
        dest = Stop.objects.create(route=route, name="Destino 2", order=2)
        trip = Trip.objects.create(
            bus=self.bus,
            route=route,
            origin=origin,
            destination=dest,
            departure_time=timezone.now(),
            arrival_time=timezone.now() + timezone.timedelta(hours=2),
            price=50000,
        )
        for s in (seat_01, seat_1):
            sale = Sale.objects.create(
                user=user,
                trip=trip,
                seat=s,
                amount=50000,
                status=Sale.Status.PAID,
            )
            Ticket.objects.create(
                sale=sale,
                trip=trip,
                seat=s,
                ticket_number=f"TK-{s.seat_number}",
                status=Ticket.Status.ISSUED,
            )

        from DjangoProject1.apps.fleet.services import reconcile_bus_seats
        res = reconcile_bus_seats(self.bus, dry_run=False)
        # Debe detenerse y exigir auditoría manual sin borrar ninguno
        self.assertTrue(res["requires_manual_audit"])
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 2)


class DriverUnifiedCreationTests(TestCase):
    def test_create_driver_without_user_id_creates_driver_user_automatically(self):
        from DjangoProject1.apps.accounts.models import User
        from DjangoProject1.apps.fleet.models import Driver
        from DjangoProject1.apps.fleet.serializers import DriverSerializer

        data = {
            "full_name": "Juan Pérez Conductor",
            "license_number": "LIC-998877",
            "address": "Calle 45 # 10-20",
            "phone_number": "3109876543",
            "email": "juan.conductor@example.com",
            "identification_number": "1098765432",
            "identification_document_code": "13",
        }

        serializer = DriverSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        driver = serializer.save()

        self.assertIsNotNone(driver.user)
        self.assertEqual(driver.user.role, User.Role.DRIVER)
        self.assertEqual(driver.user.identification_number, "1098765432")
        self.assertEqual(driver.user.email, "juan.conductor@example.com")
        self.assertEqual(driver.user.first_name, "Juan")
        self.assertEqual(driver.user.last_name, "Pérez Conductor")
        self.assertTrue(driver.user.password_change_required)
        # La contraseña por defecto es la identificación
        self.assertTrue(driver.user.check_password("1098765432"))

    def test_create_driver_with_existing_driver_user_succeeds(self):
        from DjangoProject1.apps.accounts.models import User
        from DjangoProject1.apps.fleet.models import Driver
        from DjangoProject1.apps.fleet.serializers import DriverSerializer

        existing_user = User.objects.create_user(
            username="existing_driver_user",
            email="existing_driver@example.com",
            identification_number="88887777",
            role=User.Role.DRIVER,
            password="securepassword",
        )

        data = {
            "full_name": "Pedro Existente",
            "license_number": "LIC-EXIST-1",
            "address": "Carrera 7 # 12-34",
            "phone_number": "3000000001",
            "user": existing_user.id,
        }

        serializer = DriverSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        driver = serializer.save()

        self.assertEqual(driver.user.id, existing_user.id)
        self.assertEqual(driver.user.role, User.Role.DRIVER)

    def test_create_driver_with_client_user_role_fails_validation(self):
        from DjangoProject1.apps.accounts.models import User
        from DjangoProject1.apps.fleet.serializers import DriverSerializer

        client_user = User.objects.create_user(
            username="client_user_1",
            email="client1@example.com",
            identification_number="11112222",
            role=User.Role.CLIENT,
            password="securepassword",
        )

        data = {
            "full_name": "Intento Fallido",
            "license_number": "LIC-FAIL",
            "address": "Av 1",
            "phone_number": "3000000002",
            "user": client_user.id,
        }

        serializer = DriverSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("user", serializer.errors)
