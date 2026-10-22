from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0006_make_trip_operational_fields_optional"),
    ]

    operations = [
        migrations.CreateModel(
            name="TripFare",
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
                ("amount_cents", models.PositiveIntegerField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "trip",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fare",
                        to="trips.trip",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tarifa de viaje",
                "verbose_name_plural": "Tarifas de viajes",
            },
        ),
    ]
