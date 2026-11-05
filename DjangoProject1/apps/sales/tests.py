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
