from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sales", "0004_sale_expires_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="Purchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_cents", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("paid", "Pagada"), ("failed", "Fallida"), ("cancelled", "Cancelada"), ("expired", "Expirada")], default="pending", max_length=20)),
                ("reference", models.CharField(max_length=120, unique=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchases", to=settings.AUTH_USER_MODEL)),
                ("trip", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="trips.trip")),
            ],
        ),
        migrations.AddField(
            model_name="sale",
            name="purchase",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales", to="sales.purchase"),
        ),
        migrations.AddField(
            model_name="payment",
            name="purchase",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment", to="sales.purchase"),
        ),
    ]
