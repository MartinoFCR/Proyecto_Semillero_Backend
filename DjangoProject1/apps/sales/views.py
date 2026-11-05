import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from DjangoProject1.apps.fleet.models import Seat
from DjangoProject1.apps.trips.models import Trip
from .models import Payment, Sale, SaleItem, Ticket
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
    validate_wompi_event_signature,
    wompi_integrity_signature,
    send_sale_confirmation_email,
)
from .ticket_verification import get_ticket_from_verification_token

User = get_user_model()

class SaleViewSet(ReadOnlyModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSaleOwner]

    def get_queryset(self):
        queryset = Sale.objects.select_related(
            "buyer",
            "created_by",
            "trip__route__origin",
            "trip__route__destination",
        ).prefetch_related("tickets", "payment", "items")
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


class TicketVerificationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "").strip()
        if not token:
            return Response(
                {"valid": False, "detail": "El token es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ticket = get_ticket_from_verification_token(token)
        except (
            signing.BadSignature,
            signing.SignatureExpired,
            Ticket.DoesNotExist,
        ):
            return Response(
                {"valid": False, "detail": "El tiquete no es válido."},
                status=status.HTTP_404_NOT_FOUND,
            )
        identification = ticket.passenger_identification
        masked_identification = (
            f"{'*' * max(len(identification) - 4, 0)}"
            f"{identification[-4:]}"
        )
        response = Response({
            "valid": ticket.status == Ticket.Status.ISSUED,
            "status": ticket.status,
            "ticket_code": str(ticket.ticket_code),
            "trip": {
                "id": ticket.trip_id,
                "origin": ticket.trip.route.origin.place_name,
                "destination": ticket.trip.route.destination.place_name,
                "date_time_start": ticket.trip.date_time_start,
                "date_time_end": ticket.trip.date_time_end,
            },
            "passenger": {
                "name": ticket.passenger_name.split(" ")[0],
                "identification_number": masked_identification,
            },
            "seat": {
                "id": ticket.seat_id,
                "seat_number": ticket.seat.seat_number,
            },
        })
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response


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
                    customer.password_change_required = True
                    customer.is_active = True
                    customer.save(update_fields=[
                        "password",
                        "password_change_required",
                        "is_active",
                    ])

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
                passenger_identification_document_code=request.data.get(
                    "identification_document_code",
                    "",
                ),
                passenger_name=request.data["name"],
                passenger_email=request.data["email"],
                passenger_telephone=request.data["telephone"],
            )
            SaleItem.objects.create(
                sale=sale,
                trip=trip,
                seat=seat,
                passenger_identification=request.data["identification_number"],
                passenger_identification_document_code=request.data.get(
                    "identification_document_code",
                    "",
                ),
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
                    "identification_document_code": request.data.get(
                        "identification_document_code",
                        "",
                    ),
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


class SaleInvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, sale_id):
        sale = Sale.objects.select_related("buyer").filter(pk=sale_id).first()
        if sale is None:
            return Response(
                {"detail": "La venta no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.user.role != "admin" and sale.buyer_id != request.user.id:
            return Response(
                {"detail": "No puedes consultar esta factura."},
                status=status.HTTP_403_FORBIDDEN,
            )
        invoice = getattr(sale, "factus_invoice", None)
        if invoice is None:
            return Response({
                "sale_id": sale.id,
                "status": "pending",
                "detail": "La factura todavía no ha sido generada.",
            })
        return Response(FactusInvoiceSerializer(invoice).data)


class SaleConfirmationResendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, sale_id):
        sale = Sale.objects.filter(pk=sale_id).first()
        if sale is None:
            return Response({"detail": "La venta no existe."}, status=status.HTTP_404_NOT_FOUND)
        if request.user.role != "admin" and sale.buyer_id != request.user.id:
            return Response({"detail": "No puedes reenviar esta confirmación."}, status=status.HTTP_403_FORBIDDEN)
        if sale.status != Sale.Status.PAID:
            return Response(
                {"code": "sale_not_paid", "detail": "Solo se puede confirmar una compra pagada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not send_sale_confirmation_email(sale.id, force=True):
            return Response(
                {"code": "email_unavailable", "detail": "No fue posible enviar el correo."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {"detail": "Se solicitó el reenvío de la confirmación."},
            status=status.HTTP_202_ACCEPTED,
        )


class WompiCheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    max_tickets = 10

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response(
                {"detail": "El encabezado Idempotency-Key es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing_sale = Sale.objects.filter(
            idempotency_key=idempotency_key,
        ).first()
        if existing_sale:
            if existing_sale.buyer_id != request.user.id:
                return Response(
                    {"detail": "La clave de idempotencia ya está en uso."},
                    status=status.HTTP_409_CONFLICT,
                )
            return self._widget_response(existing_sale, status.HTTP_200_OK)

        passengers = request.data.get("passengers")
        if passengers is None:
            passengers = [{
                "seat": request.data.get("seat"),
                "name": (
                    f"{request.user.first_name} {request.user.last_name}"
                ).strip(),
                "identification_document_code": (
                    request.user.identification_document_code
                ),
                "identification_number": request.user.identification_number,
                "email": request.user.email,
                "telephone": request.user.telephone or "",
            }]
        if not isinstance(passengers, list) or not passengers:
            return Response(
                {"passengers": "Debe enviar al menos un pasajero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(passengers) > self.max_tickets:
            return Response(
                {
                    "passengers": (
                        f"Una compra permite máximo {self.max_tickets} boletas."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            trip = Trip.objects.select_related("bus", "fare").get(
                pk=request.data["trip"],
                trip_state=Trip.TripState.SCHEDULED,
            )
            amount_cents = trip.fare.amount_cents
        except (
            KeyError,
            Trip.DoesNotExist,
            ObjectDoesNotExist,
            ValueError,
            TypeError,
        ):
            return Response(
                {"detail": "El viaje, la silla o el valor no es válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seats_by_id = {}
        normalized_passengers = []
        for passenger in passengers:
            if not isinstance(passenger, dict):
                return Response(
                    {"passengers": "Cada pasajero debe ser un objeto."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            required = (
                "seat",
                "name",
                "identification_number",
                "email",
            )
            missing = [field for field in required if not passenger.get(field)]
            if missing:
                return Response(
                    {"passenger": f"Faltan campos: {', '.join(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                seat_id = int(passenger["seat"])
            except (TypeError, ValueError):
                return Response(
                    {"seat": "El identificador de silla no es válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if seat_id in seats_by_id:
                return Response(
                    {"passengers": "No se puede repetir una silla."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            seats_by_id[seat_id] = True
            normalized_passengers.append({
                **passenger,
                "seat": seat_id,
                "telephone": passenger.get("telephone", ""),
                "identification_document_code": passenger.get(
                    "identification_document_code",
                    "",
                ),
            })

        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            seats = list(
                trip.bus.seats.select_for_update().filter(
                    pk__in=seats_by_id,
                ).order_by("pk")
            )
            if len(seats) != len(normalized_passengers):
                return Response(
                    {"detail": "Una silla no pertenece al bus del viaje."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            seats_by_id = {seat.pk: seat for seat in seats}
            now = timezone.now()
            for passenger in normalized_passengers:
                seat = seats_by_id[passenger["seat"]]
                if Ticket.objects.filter(
                    trip=trip,
                    seat=seat,
                    status=Ticket.Status.ISSUED,
                ).exists():
                    return Response(
                        {"detail": f"La silla {seat.seat_number} ya está vendida."},
                        status=status.HTTP_409_CONFLICT,
                    )
                holds = Sale.objects.filter(
                    trip=trip,
                    seat=seat,
                    source=Sale.Source.ONLINE,
                    status=Sale.Status.PENDING,
                ).select_for_update()
                for active_hold in holds:
                    if active_hold.expires_at and active_hold.expires_at > now:
                        return Response(
                            {
                                "detail": (
                                    f"La silla {seat.seat_number} está reservada."
                                )
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    active_hold.status = Sale.Status.EXPIRED
                    active_hold.save(update_fields=["status", "updated_at"])

            first = normalized_passengers[0]
            sale = Sale.objects.create(
                buyer=request.user,
                created_by=request.user,
                source=Sale.Source.ONLINE,
                payment_method=Sale.PaymentMethod.WOMPI,
                amount_cents=amount_cents * len(normalized_passengers),
                trip=trip,
                seat=seats_by_id[first["seat"]],
                passenger_identification=first["identification_number"],
                passenger_identification_document_code=first[
                    "identification_document_code"
                ],
                passenger_name=first["name"],
                passenger_email=first["email"],
                passenger_telephone=first["telephone"],
                expires_at=now + timedelta(minutes=5),
                idempotency_key=idempotency_key,
            )
            SaleItem.objects.bulk_create([
                SaleItem(
                    sale=sale,
                    trip=trip,
                    seat=seats_by_id[passenger["seat"]],
                    passenger_identification_document_code=passenger[
                        "identification_document_code"
                    ],
                    passenger_identification=passenger[
                        "identification_number"
                    ],
                    passenger_name=passenger["name"],
                    passenger_email=passenger["email"],
                    passenger_telephone=passenger["telephone"],
                )
                for passenger in normalized_passengers
            ])
        reference = f"sale-{sale.pk}"
        Payment.objects.create(
            sale=sale,
            provider="wompi",
            provider_reference=reference,
            amount_cents=sale.amount_cents,
        )
        return self._widget_response(sale, status.HTTP_201_CREATED)

    def _widget_response(self, sale, response_status):
        payment = sale.payment
        return Response(
            {
                "sale_id": sale.id,
                "reference": payment.provider_reference,
                "public_key": os.getenv("WOMPI_PUBLIC_KEY", ""),
                "currency": "COP",
                "amount_in_cents": sale.amount_cents,
                "signature_integrity": wompi_integrity_signature(
                    payment.provider_reference,
                    sale.amount_cents,
                ),
                "redirect_url": self.request.data.get("redirect_url", ""),
                "expires_at": sale.expires_at,
                "server_time": timezone.now(),
                "quantity": sale.quantity,
            },
            status=response_status,
        )


class WompiWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not validate_wompi_event_signature(request.data):
            return Response({"detail": "Firma de evento inválida."}, status=400)
        transaction_data = request.data["data"]["transaction"]
        reference = transaction_data.get("reference", "")
        try:
            sale = Sale.objects.get(payment__provider_reference=reference)
        except Sale.DoesNotExist:
            return Response({"detail": "Venta no encontrada."}, status=404)
        if (
            transaction_data.get("amount_in_cents") != sale.amount_cents
            or transaction_data.get("currency") != "COP"
        ):
            return Response({"detail": "El valor del pago no coincide."}, status=400)
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
        transaction_id = request.data.get("transaction_id")
        if not sale_id or not transaction_id:
            return Response(
                {"detail": "sale_id y transaction_id son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sale = Sale.objects.select_related("buyer").get(pk=sale_id)
        except (Sale.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "La venta no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if (
            request.user.role != "admin"
            and sale.buyer_id != request.user.id
        ):
            return Response(
                {"detail": "No puedes consultar esta venta."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if (
            sale.status == Sale.Status.PENDING
            and sale.expires_at
            and sale.expires_at <= timezone.now()
        ):
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
            != sale.payment.provider_reference
            or transaction_data.get("amount_in_cents") != sale.amount_cents
            or transaction_data.get("currency") != "COP"
        ):
            return Response(
                {"detail": "La transacción no coincide con la venta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_status = transaction_data.get("status", "ERROR")
        if transaction_status in {"APPROVED", "DECLINED", "ERROR"}:
            mark_sale_paid(
                sale,
                transaction_status,
                None,
                wompi_response,
            )
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
