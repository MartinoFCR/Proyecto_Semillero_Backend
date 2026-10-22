from rest_framework import serializers

from .models import FactusInvoice, Payment, Sale, Ticket


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = "__all__"
        read_only_fields = ("ticket_code", "issued_at", "status")


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
            "expires_at",
        )


class SaleSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    factus_invoice = FactusInvoiceSerializer(read_only=True)

    class Meta:
        model = Sale
        fields = "__all__"
        read_only_fields = (
            "buyer",
            "created_by",
            "source",
            "status",
            "created_at",
            "updated_at",
        )
