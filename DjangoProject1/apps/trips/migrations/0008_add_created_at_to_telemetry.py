from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0007_tripfare"),
    ]

    operations = [
        migrations.AddField(
            model_name="reading",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                help_text="Timestamp de recepción en el servidor",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="reading",
            name="time_stamp",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text="Timestamp original del sensor/GPS del ESP32",
            ),
        ),
        migrations.AddField(
            model_name="seatsstaterecord",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                help_text="Timestamp de recepción en el servidor",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="seatsstaterecord",
            name="time_stamp",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text="Timestamp original del sensor/GPS del ESP32",
            ),
        ),
    ]
