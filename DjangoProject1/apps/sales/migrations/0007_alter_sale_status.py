from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0006_passenger_document_codes"),
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
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
