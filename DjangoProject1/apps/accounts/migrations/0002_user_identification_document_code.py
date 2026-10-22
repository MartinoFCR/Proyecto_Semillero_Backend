from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="identification_document_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("13", "Cédula de ciudadanía"),
                    ("22", "Cédula de extranjería"),
                    ("41", "Pasaporte"),
                    ("12", "Tarjeta de identidad"),
                ],
                default="",
                max_length=2,
            ),
        ),
    ]
