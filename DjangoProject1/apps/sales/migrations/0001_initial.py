import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("fleet", "0001_initial"),
        ("trips", "0005_alter_trip_date_time_end"),
    ]

    operations = [
        migrations.CreateModel(
            name="Sale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("online", "Online"), ("admin", "Administrativa")], max_length=20)),
                ("payment_method", models.CharField(choices=[("wompi", "Wompi"), ("transfer", "Transferencia"), ("cash", "Efectivo"), ("card", "Tarjeta")], max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("paid", "Pagada"), ("failed", "Fallida"), ("cancelled", "Cancelada")], default="pending", max_length=20)),
                ("amount_cents", models.PositiveIntegerField()),
                ("passenger_identification", models.CharField(max_length=20)),
                ("passenger_name", models.CharField(max_length=150)),
                ("passenger_email", models.EmailField(max_length=50)),
                ("passenger_telephone", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_sales", to=settings.AUTH_USER_MODEL)),
                ("seat", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fleet.seat")),
                ("trip", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="trips.trip")),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="wompi", max_length=30)),
                ("provider_reference", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("status", models.CharField(default="PENDING", max_length=30)),
                ("amount_cents", models.PositiveIntegerField()),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("sale", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="payment", to="sales.sale")),
            ],
        ),
        migrations.CreateModel(
            name="Ticket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("passenger_identification", models.CharField(max_length=20)),
                ("passenger_name", models.CharField(max_length=150)),
                ("passenger_email", models.EmailField(max_length=50)),
                ("passenger_telephone", models.CharField(blank=True, max_length=20)),
                ("ticket_code", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(choices=[("issued", "Emitido"), ("cancelled", "Cancelado")], default="issued", max_length=20)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tickets", to="sales.sale")),
                ("seat", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fleet.seat")),
                ("trip", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="trips.trip")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("status", "issued")), fields=("trip", "seat"), name="unique_issued_ticket_trip_seat"),
                ],
            },
        ),
    ]
