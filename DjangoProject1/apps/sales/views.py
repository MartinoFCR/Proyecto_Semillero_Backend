import os

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from DjangoProject1.apps.trips.models import Trip
from .models import Payment, Sale, Ticket
from .permissions import IsAdminOrSaleOwner
from .serializers import SaleSerializer, TicketSerializer
from .services import (
    create_ticket_for_sale,
    mark_sale_paid,
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

        required = ("identification_number", "name", "email", "telephone", "trip", "seat", "amount_cents", "payment_method")
        missing = [field for field in required if field not in request.data]
        if missing:
            return Response({"detail": f"Faltan campos: {', '.join(missing)}"}, status=400)
        if request.data["payment_method"] not in {"transfer", "cash", "card"}:
            return Response({"detail": "Método de pago administrativo inválido."}, status=400)

        with transaction.atomic():
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

            trip = Trip.objects.get(pk=request.data["trip"])
            sale = Sale.objects.create(
                buyer=customer,
                created_by=request.user,
                source=Sale.Source.ADMIN,
                payment_method=request.data["payment_method"],
                status=Sale.Status.PAID,
                amount_cents=request.data["amount_cents"],
            )
            create_ticket_for_sale(
                sale,
                trip,
                trip.bus.seats.get(pk=request.data["seat"]),
                {
                    "identification_number": request.data["identification_number"],
                    "name": request.data["name"],
                    "email": request.data["email"],
                    "telephone": request.data["telephone"],
                },
            )
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class WompiCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        trip = Trip.objects.get(pk=request.data["trip"])
        amount_cents = int(request.data["amount_cents"])
        seat = trip.bus.seats.get(pk=request.data["seat"])
        if Ticket.objects.filter(
            trip=trip,
            seat=seat,
            status=Ticket.Status.ISSUED,
        ).exists():
            return Response({"detail": "La silla ya está vendida para este viaje."}, status=400)
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
        if transaction_data.get("amount_in_cents") != sale.amount_cents:
            return Response({"detail": "El valor del pago no coincide."}, status=400)
        mark_sale_paid(
            sale,
            transaction_data.get("status", "ERROR"),
            transaction_data.get("id"),
            request.data,
        )
        return Response({"detail": "Evento procesado."})
