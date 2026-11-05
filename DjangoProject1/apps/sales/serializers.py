from rest_framework import serializers

from .models import FactusInvoice, Payment, Sale, SaleItem, Ticket
from .ticket_verification import ticket_verification_token, ticket_verification_url


class TicketSerializer(serializers.ModelSerializer):
    verification_token = serializers.SerializerMethodField()
    verification_url = serializers.SerializerMethodField()
    seat_number = serializers.CharField(source="seat.seat_number", read_only=True)

    class Meta:
        model = Ticket
        fields = "__all__"
        read_only_fields = (
            "ticket_code",
            "issued_at",
            "status",
            "verification_token",
            "verification_url",
        )

    def get_verification_token(self, ticket):
        return ticket_verification_token(ticket)

    def get_verification_url(self, ticket):
        request = self.context.get("request")
        if request is None:
            return None
        return ticket_verification_url(ticket, request)


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = "__all__"
        read_only_fields = ("sale",)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("raw_response", "processed_at")


class FactusInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FactusInvoice
        fields = "__all__"
        read_only_fields = (
            "id",
            "sale",
            "status",
            "number",
            "cufe",
            "pdf_url",
            "xml_url",
            "public_url",
            "qr_url",
            "error_message",
            "raw_response",
            "created_at",
            "updated_at",
        )


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    factus_invoice = FactusInvoiceSerializer(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    unit_amount_cents = serializers.SerializerMethodField()
    route = serializers.SerializerMethodField()
    trip_start = serializers.DateTimeField(
        source="trip.date_time_start",
        read_only=True,
    )

    class Meta:
        model = Sale
        fields = (
            "id",
            "buyer",
            "created_by",
            "source",
            "payment_method",
            "status",
            "amount_cents",
            "unit_amount_cents",
            "trip",
            "seat",
            "passenger_identification",
            "passenger_name",
            "passenger_email",
            "passenger_telephone",
            "expires_at",
            "idempotency_key",
            "created_at",
            "updated_at",
            "quantity",
            "route",
            "trip_start",
            "items",
            "tickets",
            "payment",
            "factus_invoice",
        )
        read_only_fields = (
            "buyer",
            "created_by",
            "source",
            "status",
            "created_at",
            "updated_at",
            "idempotency_key",
        )

    def get_route(self, sale):
        route = sale.trip.route
        return {
            "id": route.id,
            "origin": route.origin.place_name,
            "destination": route.destination.place_name,
        }

    def get_unit_amount_cents(self, sale):
        return sale.trip.fare.amount_cents
