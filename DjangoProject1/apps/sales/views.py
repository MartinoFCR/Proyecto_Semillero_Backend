import os
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from DjangoProject1.apps.fleet.models import Seat
from DjangoProject1.apps.trips.models import Trip
from .models import Payment, Purchase, Sale, Ticket
from .permissions import IsAdminOrSaleOwner
from .serializers import (
    FactusInvoiceSerializer,
    SaleSerializer,
    TicketSerializer,
)
from .services import (
    create_ticket_for_sale,
    get_wompi_transaction,
    issue_factus_invoice,
    mark_sale_paid,
    mark_purchase_paid,
    validate_wompi_event_signature,
    wompi_integrity_signature,
)

User = get_user_model()

class SaleViewSet(ReadOnlyModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSaleOwner]

    def get_queryset(self):
        queryset = Sale.objects.select_related(
            "buyer",
            "created_by",
        ).prefetch_related("tickets", "payment")
        if self.request.user.role == "admin":
            return queryset
        return queryset.filter(buyer=self.request.user)


class TicketViewSet(ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Ticket.objects.select_related("sale", "trip", "seat")
        if self.request.user.role == "admin":
            return queryset
        return queryset.filter(sale__buyer=self.request.user)


class AdminSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "admin":
            return Response({"detail": "Solo un administrador puede registrar ventas."}, status=403)

        required = (
            "identification_number",
            "name",
            "email",
            "telephone",
            "trip",
            "seat",
            "payment_method",
        )
        missing = [field for field in required if field not in request.data]
        if missing:
            return Response(
                {"detail": f"Faltan campos: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.data["payment_method"] not in {"transfer", "cash", "card"}:
            return Response(
                {"detail": "Método de pago administrativo inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                customer, created = User.objects.get_or_create(
                    identification_number=request.data["identification_number"],
                    defaults={
                        "username": request.data["identification_number"],
                        "email": request.data["email"],
                        "first_name": request.data["name"],
                        "telephone": request.data["telephone"],
                        "role": User.Role.CLIENT,
                    },
                )
                if created:
                    customer.set_password(request.data["identification_number"])
                    customer.save(update_fields=["password"])

                trip = Trip.objects.select_related("bus", "fare").get(
                    pk=request.data["trip"]
                )
                seat = trip.bus.seats.select_for_update().get(
                    pk=request.data["seat"]
                )
                amount_cents = trip.fare.amount_cents
                active_hold = Sale.objects.filter(
                    trip=trip,
                    seat=seat,
                    source=Sale.Source.ONLINE,
                    status=Sale.Status.PENDING,
                ).first()
                if active_hold:
                    if active_hold.has_active_hold():
                        return Response(
                            {"detail": "La silla está reservada temporalmente."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    active_hold.status = Sale.Status.EXPIRED
                    active_hold.save(update_fields=["status", "updated_at"])
            except (
                Seat.DoesNotExist,
                Trip.DoesNotExist,
                ObjectDoesNotExist,
                ValueError,
                TypeError,
            ):
                return Response(
                    {"detail": "El viaje o el valor de la venta no es válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            sale = Sale.objects.create(
                buyer=customer,
                created_by=request.user,
                source=Sale.Source.ADMIN,
                payment_method=request.data["payment_method"],
                status=Sale.Status.PAID,
                amount_cents=amount_cents,
                trip=trip,
                seat=seat,
                passenger_identification=request.data["identification_number"],
                passenger_name=request.data["name"],
                passenger_email=request.data["email"],
                passenger_telephone=request.data["telephone"],
            )
            create_ticket_for_sale(
                sale,
                trip,
                seat,
                {
                    "identification_number": request.data["identification_number"],
                    "name": request.data["name"],
                    "email": request.data["email"],
                    "telephone": request.data["telephone"],
                },
            )
            transaction.on_commit(
                lambda sale_id=sale.pk: issue_factus_invoice(sale_id)
            )
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class FactusInvoiceRetryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sale_id):
        if request.user.role != "admin":
            return Response(
                {"detail": "Solo un administrador puede reintentar facturas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            invoice = issue_factus_invoice(sale_id)
        except Sale.DoesNotExist:
            return Response(
                {"detail": "La venta no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(FactusInvoiceSerializer(invoice).data)


class WompiCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            trip = Trip.objects.select_related("bus", "fare").get(
                pk=request.data["trip"]
            )
            seat = trip.bus.seats.get(pk=request.data["seat"])
            amount_cents = trip.fare.amount_cents
        except (
            KeyError,
            Seat.DoesNotExist,
            Trip.DoesNotExist,
            ObjectDoesNotExist,
            ValueError,
            TypeError,
        ):
            return Response(
                {"detail": "El viaje, la silla o el valor no es válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Ticket.objects.filter(
            trip=trip,
            seat=seat,
            status=Ticket.Status.ISSUED,
        ).exists():
            return Response(
                {"detail": "La silla ya está vendida para este viaje."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            seat = trip.bus.seats.select_for_update().get(pk=seat.pk)
            active_hold = Sale.objects.filter(
                trip=trip,
                seat=seat,
                source=Sale.Source.ONLINE,
                status=Sale.Status.PENDING,
            ).first()
            if active_hold:
                if active_hold.has_active_hold():
                    return Response(
                        {"detail": "La silla está reservada temporalmente."},
                        status=status.HTTP_409_CONFLICT,
                    )
                active_hold.status = Sale.Status.EXPIRED
                active_hold.save(update_fields=["status", "updated_at"])
            sale = Sale.objects.create(
                buyer=request.user,
                created_by=request.user,
                source=Sale.Source.ONLINE,
                payment_method=Sale.PaymentMethod.WOMPI,
                amount_cents=amount_cents,
                trip=trip,
                seat=seat,
                passenger_identification=request.user.identification_number,
                passenger_name=f"{request.user.first_name} {request.user.last_name}".strip(),
                passenger_email=request.user.email,
                passenger_telephone=request.user.telephone or "",
                expires_at=timezone.now() + timedelta(minutes=5),
            )
        reference = f"sale-{sale.pk}"
        Payment.objects.create(
            sale=sale,
            provider="wompi",
            provider_reference=reference,
            amount_cents=amount_cents,
        )
        return Response({
            "sale_id": sale.id,
            "reference": reference,
            "public_key": os.getenv("WOMPI_PUBLIC_KEY", ""),
            "currency": "COP",
            "amount_in_cents": amount_cents,
            "signature_integrity": wompi_integrity_signature(reference, amount_cents),
            "redirect_url": request.data.get("redirect_url", ""),
        }, status=status.HTTP_201_CREATED)


class WompiMultiCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        passengers = request.data.get("passengers")
        if not isinstance(passengers, list) or not passengers:
            return Response(
                {"passengers": "Debe incluir al menos un pasajero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            trip = Trip.objects.select_related("bus", "fare").get(
                pk=request.data["trip"],
                trip_state=Trip.TripState.SCHEDULED,
            )
            amount_cents = trip.fare.amount_cents
            seat_ids = [item["seat"] for item in passengers]
            if len(seat_ids) != len(set(seat_ids)):
                raise ValueError("No puede repetir sillas.")
            seats = list(
                trip.bus.seats.select_for_update().filter(id__in=seat_ids)
            )
            if len(seats) != len(seat_ids):
                raise ValueError("Una silla no pertenece al viaje.")
        except (KeyError, ValueError, TypeError, Trip.DoesNotExist,
                ObjectDoesNotExist):
            return Response(
                {"detail": "El viaje o los pasajeros no son válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            locked = list(
                trip.bus.seats.select_for_update().filter(id__in=seat_ids)
            )
            sold = set(Ticket.objects.filter(
                trip=trip, seat_id__in=seat_ids,
                status=Ticket.Status.ISSUED,
            ).values_list("seat_id", flat=True))
            held = Sale.objects.filter(
                trip=trip, seat_id__in=seat_ids,
                source=Sale.Source.ONLINE, status=Sale.Status.PENDING,
                expires_at__gt=timezone.now(),
            ).values_list("seat_id", flat=True)
            unavailable = sold | set(held)
            if unavailable:
                return Response(
                    {"detail": "Una o más sillas no están disponibles.",
                     "seat_ids": list(unavailable)},
                    status=status.HTTP_409_CONFLICT,
                )
            purchase = Purchase.objects.create(
                buyer=request.user,
                trip=trip,
                amount_cents=amount_cents * len(passengers),
                reference=f"purchase-{uuid.uuid4().hex}",
                expires_at=timezone.now() + timedelta(minutes=5),
            )
            seat_map = {seat.id: seat for seat in locked}
            for passenger in passengers:
                required = ("seat", "name", "identification_number", "email")
                if any(field not in passenger for field in required):
                    transaction.set_rollback(True)
                    return Response(
                        {"detail": "Faltan datos de pasajero."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                Sale.objects.create(
                    purchase=purchase,
                    buyer=request.user,
                    created_by=request.user,
                    source=Sale.Source.ONLINE,
                    payment_method=Sale.PaymentMethod.WOMPI,
                    amount_cents=amount_cents,
                    trip=trip,
                    seat=seat_map[passenger["seat"]],
                    passenger_identification=passenger["identification_number"],
                    passenger_name=passenger["name"],
                    passenger_email=passenger["email"],
                    passenger_telephone=passenger.get("telephone", ""),
                    expires_at=purchase.expires_at,
                )
            Payment.objects.create(
                purchase=purchase,
                provider="wompi",
                provider_reference=purchase.reference,
                amount_cents=purchase.amount_cents,
            )
        return Response({
            "purchase_id": purchase.id,
            "sale_ids": list(purchase.sales.values_list("id", flat=True)),
            "reference": purchase.reference,
            "expires_at": purchase.expires_at,
            "public_key": os.getenv("WOMPI_PUBLIC_KEY", ""),
            "currency": "COP",
            "amount_in_cents": purchase.amount_cents,
            "signature_integrity": wompi_integrity_signature(
                purchase.reference, purchase.amount_cents
            ),
            "redirect_url": request.data.get("redirect_url", ""),
        }, status=status.HTTP_201_CREATED)


class WompiWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not validate_wompi_event_signature(request.data):
            return Response({"detail": "Firma de evento inválida."}, status=400)
        transaction_data = request.data["data"]["transaction"]
        reference = transaction_data.get("reference", "")
        try:
            sale = Sale.objects.get(payment__provider_reference=reference)
            purchase = None
        except Sale.DoesNotExist:
            try:
                purchase = Purchase.objects.get(reference=reference)
                sale = None
            except Purchase.DoesNotExist:
                return Response({"detail": "Compra no encontrada."}, status=404)
        expected_amount = purchase.amount_cents if purchase else sale.amount_cents
        if (
            transaction_data.get("amount_in_cents") != expected_amount
            or transaction_data.get("currency") != "COP"
        ):
            return Response({"detail": "El valor del pago no coincide."}, status=400)
        if purchase:
            mark_purchase_paid(
                purchase,
                transaction_data.get("status", "ERROR"),
                request.data,
            )
        else:
            mark_sale_paid(
                sale,
                transaction_data.get("status", "ERROR"),
                None,
                request.data,
            )
        return Response({"detail": "Evento procesado."})


class WompiTransactionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sale_id = request.data.get("sale_id")
        purchase_id = request.data.get("purchase_id")
        transaction_id = request.data.get("transaction_id")
        if (not sale_id and not purchase_id) or not transaction_id:
            return Response(
                {
                    "detail": (
                        "sale_id o purchase_id y transaction_id "
                        "son obligatorios."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if purchase_id:
            try:
                purchase = Purchase.objects.select_related("buyer").get(
                    pk=purchase_id
                )
                sale = None
            except (Purchase.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "La compra no existe."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            try:
                sale = Sale.objects.select_related("buyer").get(pk=sale_id)
                purchase = None
            except (Sale.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "La venta no existe."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        owner = purchase.buyer_id if purchase else sale.buyer_id
        if request.user.role != "admin" and owner != request.user.id:
            return Response(
                {"detail": "No puedes consultar esta compra."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if purchase:
            if (
                purchase.status == Sale.Status.PENDING
                and not purchase.has_active_hold()
            ):
                purchase.status = Sale.Status.EXPIRED
                purchase.save(update_fields=["status", "updated_at"])
                return Response({
                    "purchase_id": purchase.id,
                    "sale_status": purchase.status,
                    "transaction_status": "EXPIRED",
                    "tickets": [],
                })
            reference = purchase.reference
            amount_cents = purchase.amount_cents
        else:
            reference = sale.payment.provider_reference
            amount_cents = sale.amount_cents

        if sale and sale.status == Sale.Status.PENDING and sale.expires_at and sale.expires_at <= timezone.now():
            sale.status = Sale.Status.EXPIRED
            sale.save(update_fields=["status", "updated_at"])
            return Response({
                "sale_id": sale.id,
                "sale_status": sale.status,
                "transaction_status": "EXPIRED",
                "tickets": [],
            })

        wompi_response = get_wompi_transaction(transaction_id)
        transaction_data = wompi_response.get("data", {})
        if (
            transaction_data.get("reference")
            != reference
            or transaction_data.get("amount_in_cents") != amount_cents
            or transaction_data.get("currency") != "COP"
        ):
            return Response(
                {"detail": "La transacción no coincide con la venta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_status = transaction_data.get("status", "ERROR")
        if transaction_status in {"APPROVED", "DECLINED", "ERROR"}:
            if purchase:
                mark_purchase_paid(
                    purchase,
                    transaction_status,
                    wompi_response,
                )
            else:
                mark_sale_paid(
                    sale,
                    transaction_status,
                    None,
                    wompi_response,
                )

        if purchase:
            purchase.refresh_from_db()
            tickets = Ticket.objects.filter(sale__purchase=purchase)
            return Response({
                "purchase_id": purchase.id,
                "sale_status": purchase.status,
                "transaction_status": transaction_status,
                "tickets": TicketSerializer(tickets, many=True).data,
            })
        sale.refresh_from_db()
        return Response({
            "sale_id": sale.id,
            "sale_status": sale.status,
            "transaction_status": transaction_status,
            "tickets": TicketSerializer(
                sale.tickets.all(),
                many=True,
            ).data,
        })
