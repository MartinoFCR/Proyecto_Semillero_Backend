import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from DjangoProject1.apps.fleet.models import Seat
from DjangoProject1.apps.trips.models import Trip


class Sale(models.Model):
    class Source(models.TextChoices):
        ONLINE = "online", "Online"
        ADMIN = "admin", "Administrativa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PAID = "paid", "Pagada"
        FAILED = "failed", "Fallida"
        CANCELLED = "cancelled", "Cancelada"
        EXPIRED = "expired", "Expirada"

    class PaymentMethod(models.TextChoices):
        WOMPI = "wompi", "Wompi"
        TRANSFER = "transfer", "Transferencia"
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_sales",
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount_cents = models.PositiveIntegerField()
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT)
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT)
    passenger_identification = models.CharField(max_length=20)
    passenger_name = models.CharField(max_length=150)
    passenger_email = models.EmailField(max_length=50)
    passenger_telephone = models.CharField(max_length=20, blank=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def has_active_hold(self):
        return (
            self.source == self.Source.ONLINE
            and self.status == self.Status.PENDING
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )


class Payment(models.Model):
    sale = models.OneToOneField(
        Sale,
        on_delete=models.PROTECT,
        related_name="payment",
    )
    provider = models.CharField(max_length=30, default="wompi")
    provider_reference = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        unique=True,
    )
    status = models.CharField(max_length=30, default="PENDING")
    amount_cents = models.PositiveIntegerField()
    raw_response = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(blank=True, null=True)


class FactusInvoice(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ISSUED = "issued", "Emitida"
        ERROR = "error", "Error"

    sale = models.OneToOneField(
        Sale,
        on_delete=models.PROTECT,
        related_name="factus_invoice",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    number = models.CharField(max_length=60, blank=True)
    cufe = models.CharField(max_length=255, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    xml_url = models.URLField(max_length=500, blank=True)
    public_url = models.URLField(max_length=500, blank=True)
    qr_url = models.URLField(max_length=500, blank=True)
    error_message = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Ticket(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Emitido"
        CANCELLED = "cancelled", "Cancelado"

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT)
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT)
    passenger_identification = models.CharField(max_length=20)
    passenger_name = models.CharField(max_length=150)
    passenger_email = models.EmailField(max_length=50)
    passenger_telephone = models.CharField(max_length=20, blank=True)
    ticket_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ISSUED,
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "seat"],
                condition=models.Q(status="issued"),
                name="unique_issued_ticket_trip_seat",
            ),
        ]
