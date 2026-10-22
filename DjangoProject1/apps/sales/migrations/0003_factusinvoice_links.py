from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_factusinvoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="factusinvoice",
            name="public_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="factusinvoice",
            name="qr_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
