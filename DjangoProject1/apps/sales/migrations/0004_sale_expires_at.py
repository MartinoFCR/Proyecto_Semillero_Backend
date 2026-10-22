from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_factusinvoice_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
