from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0002_systemerrorlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
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
                    "actor_name",
                    models.CharField(
                        blank=True,
                        default="Sistema Automático",
                        help_text="Nombre y rol congelado de quien ejecutó la acción (ej. 'Conductor Pepe Alfredo').",
                        max_length=160,
                    ),
                ),
                (
                    "actor_role",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="system",
                        max_length=30,
                    ),
                ),
                (
                    "module",
                    models.CharField(
                        choices=[
                            ("accounts", "Cuentas y Roles"),
                            ("trips", "Viajes y Despacho"),
                            ("sales", "Ventas y Tiquetes"),
                            ("fleet", "Flota, Conductores y GPS"),
                            ("support", "Soporte y Sistema"),
                        ],
                        db_index=True,
                        default="support",
                        max_length=30,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        db_index=True,
                        help_text="Código de acción (ej. TRIP_COMPLETED, TRIP_CANCELLED, ADMIN_CREATED, ADMIN_SALE_CREATED).",
                        max_length=60,
                    ),
                ),
                (
                    "target_model",
                    models.CharField(blank=True, default="", max_length=60),
                ),
                (
                    "target_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=60
                    ),
                ),
                (
                    "summary",
                    models.TextField(
                        help_text="Descripción legible con firma de atribución (ej. 'Este viaje #45 fue finalizado — ATT: Conductor Pepe Alfredo')."
                    ),
                ),
                ("previous_data", models.JSONField(blank=True, null=True)),
                ("new_data", models.JSONField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Registro de Auditoría",
                "verbose_name_plural": "Registros de Auditoría",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
