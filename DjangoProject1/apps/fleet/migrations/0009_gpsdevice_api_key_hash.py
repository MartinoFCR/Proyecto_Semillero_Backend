from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0008_add_gpsdevice_model"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="gpsdevice",
            name="api_key",
        ),
        migrations.AddField(
            model_name="gpsdevice",
            name="api_key_hash",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Hash seguro (PBKDF2/SHA256) de la clave o token del dispositivo.",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="gpsdevice",
            name="api_key_prefix",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Prefijo visible del token (ej. 'esp_live_a1b2...') para que el usuario identifique cuál clave tiene.",
                max_length=16,
            ),
        ),
    ]
