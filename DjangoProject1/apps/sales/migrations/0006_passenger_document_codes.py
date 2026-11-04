from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0005_saleitem_sale_idempotency_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="passenger_identification_document_code",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
        migrations.AddField(
            model_name="saleitem",
            name="passenger_identification_document_code",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
        migrations.AddField(
            model_name="ticket",
            name="passenger_identification_document_code",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
    ]
