from django.conf import settings
from django.db import models

from DjangoProject1.apps.sales.models import Sale


class SupportRequest(models.Model):
    class Category(models.TextChoices):
        PAYMENT = "payment", "Pago"
        INVOICE = "invoice", "Factura"
        TICKET = "ticket", "Tiquete"
        CHANGE = "change", "Cambio"
        CANCELLATION = "cancellation", "Cancelación"
        ACCOUNT = "account", "Cuenta"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        IN_PROGRESS = "in_progress", "En progreso"
        RESOLVED = "resolved", "Resuelta"
        CLOSED = "closed", "Cerrada"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_requests",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="support_requests",
        null=True,
        blank=True,
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=5000)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
