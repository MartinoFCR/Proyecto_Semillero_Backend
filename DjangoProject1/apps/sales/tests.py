import hashlib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from rest_framework.test import APITestCase

from DjangoProject1.apps.fleet.models import Bus, Seat
from DjangoProject1.apps.geography.models import City, Department, Place
from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.sales.models import (
    AdminSaleIdempotency,
    FactusInvoice,
    Payment,
    Sale,
    SaleItem,
    Ticket,
    TicketCheckIn,
)
from DjangoProject1.apps.sales.services import mark_sale_paid
from DjangoProject1.apps.sales.ticket_verification import ticket_verification_token
from DjangoProject1.apps.trips.models import Trip, TripFare


class MultiTicketCheckoutTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="buyer",
            password="secret-pass-123",
            email="buyer@example.com",
            identification_number="100000001",
            first_name="Buyer",
            role=user_model.Role.CLIENT,
        )
        department = Department.objects.create(department_name="Santander")
        city = City.objects.create(
            city_name="Bucaramanga",
            department=department,
        )
        origin = Place.objects.create(
            place_name="Terminal Norte",
            city=city,
            place_point=Point(-73.12, 7.12),
        )
        destination = Place.objects.create(
            place_name="Terminal Sur",
            city=city,
            place_point=Point(-73.11, 7.11),
        )
        route = Route.objects.create(
            origin=origin,
            destination=destination,
            distance_km="10.00",
        )
        self.bus = Bus.objects.create(
            plate="ABC123",
            capacity=2,
            model="Test",
        )
        self.seats = [
            Seat.objects.create(
                bus=self.bus,
                seat_number=str(index),
                row="1",
                col=str(index),
            )
            for index in (1, 2)
        ]
        driver_user = user_model.objects.create_user(
            username="driver",
            password="secret-pass-123",
            email="driver@example.com",
            identification_number="100000002",
            role=user_model.Role.DRIVER,
        )
        from DjangoProject1.apps.fleet.models import Driver

        driver = Driver.objects.create(
            user=driver_user,
            full_name="Test Driver",
            license_number="LIC-1",
            address="Test address",
            phone_number="3000000000",
        )
        self.trip = Trip.objects.create(
            bus=self.bus,
            driver=driver,
            route=route,
            trip_state=Trip.TripState.SCHEDULED,
        )
        TripFare.objects.create(trip=self.trip, amount_cents=2500000)
        self.client.force_authenticate(self.user)

    def _create_admin(self, username="boarding-admin"):
        user_model = get_user_model()
        return user_model.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            identification_number=f"{len(username)}000000",
            role=user_model.Role.ADMIN,
        )

    def _create_paid_ticket(self, seat=None):
        seat = seat or self.seats[0]
        sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ADMIN,
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.PAID,
            amount_cents=2500000,
            trip=self.trip,
            seat=seat,
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )
        return Ticket.objects.create(
            sale=sale,
            trip=self.trip,
            seat=seat,
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )

    @patch(
        "DjangoProject1.apps.sales.views.wompi_integrity_signature",
        return_value="signature",
    )
    def test_checkout_creates_one_sale_for_multiple_passengers(self, _signature):
        response = self.client.post(
            reverse("wompi-checkout"),
            {
                "trip": self.trip.id,
                "passengers": [
                    {
                        "seat": self.seats[0].id,
                        "name": "Ana",
                        "identification_document_code": "13",
                        "identification_number": "200000001",
                        "email": "ana@example.com",
                    },
                    {
                        "seat": self.seats[1].id,
                        "name": "Luis",
                        "identification_document_code": "13",
                        "identification_number": "200000002",
                        "email": "luis@example.com",
                    },
                ],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="checkout-1",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["quantity"], 2)
        self.assertEqual(response.data["amount_in_cents"], 5000000)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(SaleItem.objects.count(), 2)

    @patch(
        "DjangoProject1.apps.sales.views.wompi_integrity_signature",
        return_value="signature",
    )
    def test_repeated_idempotency_key_returns_same_sale(self, _signature):
        payload = {
            "trip": self.trip.id,
            "passengers": [{
                "seat": self.seats[0].id,
                "name": "Ana",
                "identification_number": "200000001",
                "email": "ana@example.com",
            }],
        }
        first = self.client.post(
            reverse("wompi-checkout"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="checkout-2",
        )
        second = self.client.post(
            reverse("wompi-checkout"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="checkout-2",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["sale_id"], second.data["sale_id"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_duplicate_seat_is_rejected(self):
        response = self.client.post(
            reverse("wompi-checkout"),
            {
                "trip": self.trip.id,
                "passengers": [
                    {
                        "seat": self.seats[0].id,
                        "name": "Ana",
                        "identification_number": "200000001",
                        "email": "ana@example.com",
                    },
                    {
                        "seat": self.seats[0].id,
                        "name": "Luis",
                        "identification_number": "200000002",
                        "email": "luis@example.com",
                    },
                ],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="checkout-3",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_seat_catalog_is_public(self):
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("trip-seats", kwargs={"trip_id": self.trip.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["seats"][0]["status"], "available")

    def test_availability_returns_all_thirty_seats_with_statuses(self):
        from DjangoProject1.apps.fleet.services import complete_seats_for_bus
        complete_seats_for_bus(self.bus, target_capacity=30)
        all_bus_seats = list(Seat.objects.filter(bus=self.bus).order_by("id"))
        self.assertEqual(len(all_bus_seats), 30)

        # Asiento 1 vendido (ticket emitido)
        self._create_paid_ticket(all_bus_seats[0])

        # Asientos 2 y 3 reservados en una venta pendiente con SaleItem
        pending_sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            status=Sale.Status.PENDING,
            amount_cents=5000000,
            trip=self.trip,
            seat=all_bus_seats[1],
            passenger_identification="111111",
            passenger_name="Reserva 1",
            passenger_email="res1@example.com",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        SaleItem.objects.create(
            sale=pending_sale,
            trip=self.trip,
            seat=all_bus_seats[2],
            passenger_identification="222222",
            passenger_name="Reserva 2",
            passenger_email="res2@example.com",
        )

        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("trip-seats", kwargs={"trip_id": self.trip.id}),
        )

        self.assertEqual(response.status_code, 200)
        seats = response.data["seats"]
        self.assertEqual(len(seats), 30)

        seats_by_id = {s["id"]: s for s in seats}
        self.assertEqual(seats_by_id[all_bus_seats[0].id]["status"], "sold")
        self.assertEqual(seats_by_id[all_bus_seats[1].id]["status"], "reserved")
        self.assertEqual(seats_by_id[all_bus_seats[2].id]["status"], "reserved")

        available_count = sum(1 for s in seats if s["status"] == "available")
        self.assertEqual(available_count, 27)

        # Validar que ahora se permite comprar más de 10 boletas sin límite artificial
        self.client.force_authenticate(self.user)
        more_than_10_passengers = [
            {
                "seat": all_bus_seats[i].id,
                "identification_document_code": "13",
                "identification_number": f"90000{i:02d}",
                "name": f"Pasajero {i}",
                "email": f"p{i}@example.com",
            }
            for i in range(3, 15)  # 12 pasajeros
        ]
        resp_multiple = self.client.post(
            reverse("wompi-checkout"),
            {"trip": self.trip.id, "passengers": more_than_10_passengers},
            format="json",
            HTTP_IDEMPOTENCY_KEY="multi-12-test-key",
        )
        self.assertEqual(resp_multiple.status_code, 201)
        self.assertEqual(len(resp_multiple.data["seats"]), 12)

    def test_admin_sale_accepts_multiple_seats_and_creates_one_payment(self):
        admin = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            identification_number="100000003",
            role=get_user_model().Role.ADMIN,
        )
        self.client.force_authenticate(admin)
        response = self.client.post(
            reverse("admin-sale"),
            {
                "identification_number": "200000001",
                "name": "Juan Perez",
                "email": "juan@example.com",
                "telephone": "3001234567",
                "trip": self.trip.id,
                "seats": [seat.id for seat in self.seats],
                "payment_method": "cash",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-1",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["quantity"], 2)
        self.assertEqual(response.data["amount_cents"], 5000000)
        self.assertEqual(response.data["tickets"][0]["seat_number"], "1")
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(AdminSaleIdempotency.objects.count(), 1)

    def test_admin_sale_rejects_all_seats_when_one_is_reserved(self):
        admin = get_user_model().objects.create_user(
            username="admin-reserved",
            email="admin-reserved@example.com",
            identification_number="100000004",
            role=get_user_model().Role.ADMIN,
        )
        Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            status=Sale.Status.PENDING,
            amount_cents=2500000,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000010",
            passenger_name="Reserva",
            passenger_email="reserva@example.com",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.client.force_authenticate(admin)
        response = self.client.post(
            reverse("admin-sale"),
            {
                "identification_number": "200000011",
                "name": "Juan Perez",
                "email": "juan2@example.com",
                "telephone": "3001234567",
                "trip": self.trip.id,
                "seats": [seat.id for seat in self.seats],
                "payment_method": "cash",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "seats_unavailable")
        self.assertEqual(response.data["unavailable_seats"][0]["reason"], "reserved")
        self.assertEqual(Sale.objects.filter(source=Sale.Source.ADMIN).count(), 0)

    def test_admin_sale_idempotency_rejects_changed_content(self):
        admin = get_user_model().objects.create_user(
            username="admin-idempotent",
            email="admin-idempotent@example.com",
            identification_number="100000005",
            role=get_user_model().Role.ADMIN,
        )
        self.client.force_authenticate(admin)
        payload = {
            "identification_number": "200000012",
            "name": "Juan Perez",
            "email": "juan3@example.com",
            "telephone": "3001234567",
            "trip": self.trip.id,
            "seat": self.seats[0].id,
            "payment_method": "cash",
        }
        first = self.client.post(
            reverse("admin-sale"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-2",
        )
        second = self.client.post(
            reverse("admin-sale"),
            {**payload, "telephone": "3000000000"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-2",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_admin_sale_idempotency_returns_original_sale(self):
        admin = get_user_model().objects.create_user(
            username="admin-replay",
            email="admin-replay@example.com",
            identification_number="100000006",
            role=get_user_model().Role.ADMIN,
        )
        self.client.force_authenticate(admin)
        payload = {
            "identification_number": "200000013",
            "name": "Juan Perez",
            "email": "juan4@example.com",
            "telephone": "3001234567",
            "trip": self.trip.id,
            "seat": self.seats[0].id,
            "payment_method": "cash",
        }
        first = self.client.post(
            reverse("admin-sale"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-3",
        )
        second = self.client.post(
            reverse("admin-sale"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-3",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Sale.objects.filter(source=Sale.Source.ADMIN).count(), 1)

    def test_admin_sale_is_forbidden_for_client(self):
        response = self.client.post(
            reverse("admin-sale"),
            {
                "identification_number": "200000014",
                "name": "Juan Perez",
                "email": "juan5@example.com",
                "telephone": "3001234567",
                "trip": self.trip.id,
                "seat": self.seats[0].id,
                "payment_method": "cash",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_check_in_marks_paid_ticket_used_and_audits_operator(self):
        ticket = self._create_paid_ticket()
        admin = self._create_admin()
        self.client.force_authenticate(admin)

        response = self.client.post(
            reverse("ticket-check-in"),
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-1",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Ticket.Status.USED)
        self.assertEqual(response.data["check_in"]["checked_in_by"]["id"], admin.id)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.USED)
        self.assertEqual(TicketCheckIn.objects.count(), 1)

    def test_check_in_replay_returns_original_result(self):
        ticket = self._create_paid_ticket()
        admin = self._create_admin("boarding-replay")
        self.client.force_authenticate(admin)
        payload = {
            "verification_token": ticket_verification_token(ticket),
            "trip": self.trip.id,
        }

        first = self.client.post(
            reverse("ticket-check-in"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-2",
        )
        second = self.client.post(
            reverse("ticket-check-in"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-2",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["replayed"])
        self.assertEqual(second.data["check_in"]["id"], first.data["check_in"]["id"])
        self.assertEqual(TicketCheckIn.objects.count(), 1)

    def test_check_in_rejects_idempotency_key_with_other_content(self):
        ticket = self._create_paid_ticket()
        admin = self._create_admin("boarding-conflict")
        self.client.force_authenticate(admin)
        path = reverse("ticket-check-in")
        first = self.client.post(
            path,
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-Conflict",
        )
        second = self.client.post(
            path,
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id + 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-Conflict",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "idempotency_conflict")

    @patch("DjangoProject1.apps.sales.views.TicketCheckIn.objects.create")
    def test_check_in_rolls_back_ticket_when_audit_fails(self, create_check_in):
        create_check_in.side_effect = RuntimeError("audit failure")
        ticket = self._create_paid_ticket()
        admin = self._create_admin("boarding-rollback")
        self.client.force_authenticate(admin)

        with self.assertRaises(RuntimeError):
            self.client.post(
                reverse("ticket-check-in"),
                {
                    "verification_token": ticket_verification_token(ticket),
                    "trip": self.trip.id,
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="check-in-rollback",
            )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ISSUED)
        self.assertEqual(TicketCheckIn.objects.count(), 0)

    def test_check_in_rejects_used_ticket_and_does_not_require_same_key(self):
        ticket = self._create_paid_ticket()
        admin = self._create_admin("boarding-used")
        self.client.force_authenticate(admin)
        ticket.status = Ticket.Status.USED
        ticket.save(update_fields=["status"])
        TicketCheckIn.objects.create(
            ticket=ticket,
            trip=self.trip,
            checked_in_by=admin,
        )

        response = self.client.post(
            reverse("ticket-check-in"),
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-3",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "already_used")
        self.assertEqual(TicketCheckIn.objects.count(), 1)

    def test_check_in_rejects_wrong_trip_and_client(self):
        ticket = self._create_paid_ticket()
        response = self.client.post(
            reverse("ticket-check-in"),
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id + 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-4",
        )
        self.assertEqual(response.status_code, 403)

        admin = self._create_admin("boarding-wrong-trip")
        self.client.force_authenticate(admin)
        response = self.client.post(
            reverse("ticket-check-in"),
            {
                "verification_token": ticket_verification_token(ticket),
                "trip": self.trip.id + 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="check-in-5",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "wrong_trip")

    @patch("DjangoProject1.apps.sales.services.issue_factus_invoice")
    def test_approved_payment_issues_each_ticket_only_once(self, _invoice):
        sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            amount_cents=5000000,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )
        SaleItem.objects.create(
            sale=sale,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )
        SaleItem.objects.create(
            sale=sale,
            trip=self.trip,
            seat=self.seats[1],
            passenger_identification="200000002",
            passenger_name="Luis",
            passenger_email="luis@example.com",
        )

        mark_sale_paid(sale, "APPROVED", "wompi-ref", {})
        mark_sale_paid(sale, "APPROVED", "wompi-ref", {})

        self.assertEqual(Ticket.objects.filter(sale=sale).count(), 2)

    def _create_online_sale(self, seat, minutes_ago=15, status=Sale.Status.PENDING):
        sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            status=status,
            amount_cents=2500000,
            trip=self.trip,
            seat=seat,
            passenger_identification="300000001",
            passenger_name="Tardío",
            passenger_email="late@example.com",
            expires_at=timezone.now() - timedelta(minutes=minutes_ago),
        )
        SaleItem.objects.create(
            sale=sale,
            trip=self.trip,
            seat=seat,
            passenger_identification="300000001",
            passenger_name="Tardío",
            passenger_email="late@example.com",
        )
        Payment.objects.create(
            sale=sale,
            provider="wompi",
            provider_reference=f"sale-{sale.pk}",
            amount_cents=sale.amount_cents,
        )
        return sale

    @patch("DjangoProject1.apps.sales.services.issue_factus_invoice")
    def test_late_approved_payment_issues_ticket_when_seat_free(self, _invoice):
        sale = self._create_online_sale(self.seats[0])

        sale = mark_sale_paid(sale, "APPROVED", None, {"late": True})

        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(Ticket.objects.filter(sale=sale).count(), 1)
        self.assertEqual(Payment.objects.get(sale=sale).status, "APPROVED")

    @patch("DjangoProject1.apps.sales.services.issue_factus_invoice")
    def test_late_payment_on_already_expired_sale_issues_ticket(self, _invoice):
        sale = self._create_online_sale(
            self.seats[0],
            status=Sale.Status.EXPIRED,
        )

        sale = mark_sale_paid(sale, "APPROVED", None, {})

        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(Ticket.objects.filter(sale=sale).count(), 1)

    @patch("DjangoProject1.apps.sales.services.notify_refund_required")
    @patch("DjangoProject1.apps.sales.services.issue_factus_invoice")
    def test_late_payment_with_sold_seat_requires_refund(self, invoice, notify):
        self._create_paid_ticket(self.seats[0])
        sale = self._create_online_sale(self.seats[0])

        with self.captureOnCommitCallbacks(execute=True):
            sale = mark_sale_paid(sale, "APPROVED", None, {})

        self.assertEqual(sale.status, Sale.Status.REFUND_REQUIRED)
        self.assertFalse(Ticket.objects.filter(sale=sale).exists())
        self.assertEqual(Payment.objects.get(sale=sale).status, "APPROVED")
        notify.assert_called_once_with(sale.pk)
        invoice.assert_not_called()

        # Un reintento del webhook no cambia el resultado ni duplica avisos.
        with self.captureOnCommitCallbacks(execute=True):
            mark_sale_paid(sale, "APPROVED", None, {})
        notify.assert_called_once()

    @patch("DjangoProject1.apps.sales.services.notify_refund_required")
    def test_late_payment_with_seat_held_by_other_requires_refund(self, notify):
        sale = self._create_online_sale(self.seats[0])
        other_hold = self._create_online_sale(self.seats[0], minutes_ago=-5)

        sale = mark_sale_paid(sale, "APPROVED", None, {})

        self.assertEqual(sale.status, Sale.Status.REFUND_REQUIRED)
        other_hold.refresh_from_db()
        self.assertEqual(other_hold.status, Sale.Status.PENDING)

    def test_late_declined_payment_marks_sale_expired(self):
        sale = self._create_online_sale(self.seats[0])

        sale = mark_sale_paid(sale, "DECLINED", None, {})

        self.assertEqual(sale.status, Sale.Status.EXPIRED)
        self.assertEqual(Payment.objects.get(sale=sale).status, "DECLINED")

    @patch.dict("os.environ", {"WOMPI_INTEGRITY_SECRET": "secret"})
    def test_checkout_returns_ten_minute_hold_and_expiration_signature(self):
        response = self.client.post(
            reverse("wompi-checkout"),
            {
                "trip": self.trip.pk,
                "passengers": [
                    {
                        "seat": self.seats[0].pk,
                        "identification_document_code": "13",
                        "identification_number": "200000001",
                        "name": "Ana",
                        "email": "ana@example.com",
                    },
                ],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="checkout-expiration",
        )

        self.assertEqual(response.status_code, 201, response.data)
        sale = Sale.objects.get(pk=response.data["sale_id"])
        remaining = sale.expires_at - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=9))
        self.assertLessEqual(remaining, timedelta(minutes=10))
        expiration = response.data["expiration_time"]
        self.assertRegex(expiration, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        expected = hashlib.sha256(
            f"{response.data['reference']}{sale.amount_cents}COP"
            f"{expiration}secret".encode()
        ).hexdigest()
        self.assertEqual(
            response.data["signature_integrity_with_expiration"],
            expected,
        )
        self.assertNotEqual(response.data["signature_integrity"], expected)

    def test_invoice_is_not_visible_to_another_buyer(self):
        other = get_user_model().objects.create_user(
            username="other",
            password="secret-pass-123",
            email="other@example.com",
            identification_number="100000003",
            role=get_user_model().Role.CLIENT,
        )
        sale = Sale.objects.create(
            buyer=other,
            created_by=other,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            amount_cents=2500000,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000003",
            passenger_name="Other",
            passenger_email="other@example.com",
        )
        FactusInvoice.objects.create(sale=sale)

        response = self.client.get(
            reverse("sale-invoice", kwargs={"sale_id": sale.id}),
        )

        self.assertEqual(response.status_code, 403)

    def test_ticket_qr_token_can_be_verified_without_session(self):
        sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            amount_cents=2500000,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )
        ticket = Ticket.objects.create(
            sale=sale,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="200000001",
            passenger_name="Ana",
            passenger_email="ana@example.com",
        )
        self.client.force_authenticate(None)

        ticket_response = self.client.get("/api/sales/tickets/verify/", {
            "token": ticket_verification_token(ticket),
        })

        self.assertEqual(ticket_response.status_code, 200)
        self.assertTrue(ticket_response.data["valid"])
        self.assertEqual(ticket_response.data["status"], "issued")
        self.assertEqual(ticket_response.data["ticket_code"], str(ticket.ticket_code))

        ticket.status = Ticket.Status.USED
        ticket.save(update_fields=["status"])
        used_response = self.client.get("/api/sales/tickets/verify/", {
            "token": ticket_verification_token(ticket),
        })
        self.assertEqual(used_response.status_code, 200)
        self.assertFalse(used_response.data["valid"])
        self.assertEqual(used_response.data["status"], "used")

    def test_wompi_checkout_rejects_seat_held_in_sale_item(self):
        # Cliente 1 tiene asiento 0 como principal y asiento 1 en SaleItem
        holding_sale = Sale.objects.create(
            buyer=self.user,
            created_by=self.user,
            source=Sale.Source.ONLINE,
            payment_method=Sale.PaymentMethod.WOMPI,
            status=Sale.Status.PENDING,
            amount_cents=5000000,
            trip=self.trip,
            seat=self.seats[0],
            passenger_identification="100000001",
            passenger_name="Buyer 1",
            passenger_email="buyer1@example.com",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        SaleItem.objects.create(
            sale=holding_sale,
            trip=self.trip,
            seat=self.seats[1],
            passenger_identification="100000002",
            passenger_name="Buyer 2",
            passenger_email="buyer2@example.com",
        )

        other_user = get_user_model().objects.create_user(
            username="buyer-two",
            password="secret-pass-123",
            email="otherbuyer@example.com",
            identification_number="888888888",
            role=get_user_model().Role.CLIENT,
        )
        self.client.force_authenticate(other_user)

        # Cliente 2 intenta reservar el asiento 1 (que está en SaleItem de la reserva del cliente 1)
        response = self.client.post(
            reverse("wompi-checkout"),
            {
                "trip": self.trip.id,
                "passengers": [
                    {
                        "seat": self.seats[1].id,
                        "identification_document_code": "13",
                        "identification_number": "888888888",
                        "name": "Buyer Two",
                        "email": "otherbuyer@example.com",
                    }
                ],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="conflict-checkout-key-1",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("está reservada", response.data.get("detail", ""))

    def test_admin_and_client_purchase_auto_complete_bus_seats(self):
        # Bus con capacidad 30 pero solo 2 asientos creados inicialmente
        self.bus.capacity = 30
        self.bus.save(update_fields=["capacity"])
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 2)

        # 1. Compra de cliente para asiento 15 completa los asientos automáticamente
        # Se genera el asiento 15 con el auto-complete
        from DjangoProject1.apps.fleet.services import complete_seats_for_bus
        complete_seats_for_bus(self.bus, 30)
        seat_15 = Seat.objects.get(bus=self.bus, seat_number="15")
        seat_16 = Seat.objects.get(bus=self.bus, seat_number="16")

        # Compra administrativa
        admin = self._create_admin("super-admin-seats")
        self.client.force_authenticate(admin)
        admin_resp = self.client.post(
            reverse("admin-sale"),
            {
                "trip": self.trip.id,
                "seats": [seat_15.id],
                "identification_number": "555555555",
                "name": "Pasajero Quince",
                "email": "p15@example.com",
                "telephone": "3000000015",
                "payment_method": "cash",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="admin-sale-seat-15",
        )
        self.assertEqual(admin_resp.status_code, 201)
        self.assertTrue(Ticket.objects.filter(seat=seat_15, trip=self.trip).exists())

        # Compra cliente
        self.client.force_authenticate(self.user)
        with patch("DjangoProject1.apps.sales.views.wompi_integrity_signature", return_value="sig"):
            client_resp = self.client.post(
                reverse("wompi-checkout"),
                {
                    "trip": self.trip.id,
                    "passengers": [
                        {
                            "seat": seat_16.id,
                            "identification_document_code": "13",
                            "identification_number": "666666666",
                            "name": "Pasajero Dieciséis",
                            "email": "p16@example.com",
                        }
                    ],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="client-checkout-seat-16",
            )
        self.assertEqual(client_resp.status_code, 201)
        self.assertEqual(Seat.objects.filter(bus=self.bus).count(), 30)
