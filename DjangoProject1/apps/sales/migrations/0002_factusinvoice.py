from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FactusInvoice",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("issued", "Emitida"),
                            ("error", "Error"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("number", models.CharField(blank=True, max_length=60)),
                ("cufe", models.CharField(blank=True, max_length=255)),
                ("pdf_url", models.URLField(blank=True, max_length=500)),
                ("xml_url", models.URLField(blank=True, max_length=500)),
                ("error_message", models.TextField(blank=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="factus_invoice",
                        to="sales.sale",
                    ),
                ),
            ],
        ),
    ]
