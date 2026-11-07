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


class SystemErrorLog(models.Model):
    class Level(models.TextChoices):
        WARNING = "warning", "Advertencia"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Crítico"

    class Service(models.TextChoices):
        FACTUS = "factus", "Factus (Facturación DIAN)"
        WOMPI = "wompi", "Wompi (Pasarela de Pagos)"
        TELEMETRY = "telemetry", "Telemetría / MQTT / IoT"
        SALES = "sales", "Ventas y Tiquetes"
        FLEET = "fleet", "Flota y Asignación"
        AUTH = "auth", "Autenticación"
        GENERAL = "general", "General / Sistema"

    service = models.CharField(
        max_length=30,
        choices=Service.choices,
        default=Service.GENERAL,
        db_index=True,
    )
    level = models.CharField(
        max_length=15,
        choices=Level.choices,
        default=Level.ERROR,
        db_index=True,
    )
    endpoint = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Ruta o acción donde ocurrió el error (ej. /v2/bills/validate o POST /api/fleet/devices/).",
    )
    reference_id = models.CharField(
        max_length=80,
        blank=True,
        default="",
        db_index=True,
        help_text="Identificador relacionado (ej. Venta #30, device_id 'esp2', trip #5).",
    )
    error_message = models.TextField(
        help_text="Mensaje principal o resumen legible del error.",
    )
    error_details = models.JSONField(
        blank=True,
        null=True,
        help_text="Desglose detallado de los campos rechazados o stacktrace.",
    )
    request_payload = models.JSONField(
        blank=True,
        null=True,
        help_text="Datos que se intentaron enviar al servicio.",
    )
    response_payload = models.JSONField(
        blank=True,
        null=True,
        help_text="Respuesta cruda devuelta por el servicio externo (ej. Factus, Wompi).",
    )
    status_code = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Código de estado HTTP devuelto por el servicio (ej. 422, 500).",
    )
    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indica si un administrador ya revisó o resolvió la inconsistencia.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Registro de Error del Sistema"
        verbose_name_plural = "Registros de Errores del Sistema"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.service.upper()}] ({self.level}) {self.error_message[:60]} ({self.created_at})"

