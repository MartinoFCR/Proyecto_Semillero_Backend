from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemErrorLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "service",
                    models.CharField(
                        choices=[
                            ("factus", "Factus (Facturación DIAN)"),
                            ("wompi", "Wompi (Pasarela de Pagos)"),
                            ("telemetry", "Telemetría / MQTT / IoT"),
                            ("sales", "Ventas y Tiquetes"),
                            ("fleet", "Flota y Asignación"),
                            ("auth", "Autenticación"),
                            ("general", "General / Sistema"),
                        ],
                        db_index=True,
                        default="general",
                        max_length=30,
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("warning", "Advertencia"),
                            ("error", "Error"),
                            ("critical", "Crítico"),
                        ],
                        db_index=True,
                        default="error",
                        max_length=15,
                    ),
                ),
                (
                    "endpoint",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Ruta o acción donde ocurrió el error.",
                        max_length=255,
                    ),
                ),
                (
                    "reference_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        help_text="Identificador relacionado (ej. Venta #30).",
                        max_length=80,
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        help_text="Mensaje principal o resumen legible del error."
                    ),
                ),
                (
                    "error_details",
                    models.JSONField(
                        blank=True,
                        help_text="Desglose detallado de los campos rechazados.",
                        null=True,
                    ),
                ),
                (
                    "request_payload",
                    models.JSONField(
                        blank=True,
                        help_text="Datos que se intentaron enviar al servicio.",
                        null=True,
                    ),
                ),
                (
                    "response_payload",
                    models.JSONField(
                        blank=True,
                        help_text="Respuesta cruda devuelta por el servicio externo.",
                        null=True,
                    ),
                ),
                (
                    "status_code",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Código de estado HTTP devuelto por el servicio.",
                        null=True,
                    ),
                ),
                (
                    "is_resolved",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="Indica si un administrador ya revisó o resolvió la inconsistencia.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
            ],
            options={
                "verbose_name": "Registro de Error del Sistema",
                "verbose_name_plural": "Registros de Errores del Sistema",
                "ordering": ["-created_at"],
            },
        ),
    ]
