from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0004_sale_expires_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                max_length=120,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="SaleItem",
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
                    "passenger_identification",
                    models.CharField(max_length=20),
                ),
                ("passenger_name", models.CharField(max_length=150)),
                ("passenger_email", models.EmailField(max_length=50)),
                (
                    "passenger_telephone",
                    models.CharField(blank=True, max_length=20),
                ),
                (
                    "sale",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="sales.sale",
                    ),
                ),
                (
                    "seat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="fleet.seat",
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="trips.trip",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("sale", "seat"),
                        name="unique_sale_item_seat",
                    ),
                ],
            },
        ),
    ]
