from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0011_ticketcheckin_ticketcheckinidempotency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sale",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendiente"),
                    ("paid", "Pagada"),
                    ("failed", "Fallida"),
                    ("cancelled", "Cancelada"),
                    ("expired", "Expirada"),
                    ("refund_required", "Pagada sin silla (reembolso)"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
