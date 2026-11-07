from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0008_add_created_at_to_telemetry"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="trip",
            name="state_source",
            field=models.CharField(
                choices=[("automatic", "Automático"), ("manual", "Manual")],
                default="automatic",
                help_text="Indica si el estado fue fijado manualmente por un operador o calculado automáticamente.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="trip",
            name="manual_operator",
            field=models.ForeignKey(
                blank=True,
                help_text="Operador/Administrador que realizó la última acción manual.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="operated_trips",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="trip",
            name="manual_action_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha y hora en que se ejecutó la acción manual (cancelación/finalización).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trip",
            name="cancellation_reason",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Motivo de cancelación registrado por el administrador.",
            ),
        ),
        migrations.CreateModel(
            name="TripPostponementHistory",
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
                ("previous_start", models.DateTimeField()),
                ("previous_end", models.DateTimeField(blank=True, null=True)),
                ("new_start", models.DateTimeField()),
                ("new_end", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField(help_text="Motivo de la postergación.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="postponed_trips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="postponement_history",
                        to="trips.trip",
                    ),
                ),
            ],
            options={
                "verbose_name": "Historial de postergación de viaje",
                "verbose_name_plural": "Historial de postergaciones de viajes",
                "ordering": ["-created_at"],
            },
        ),
    ]
