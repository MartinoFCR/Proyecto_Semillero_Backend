from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "trips",
            "0005_alter_trip_date_time_end",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="trip",
            name="fuel_start",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="trip",
            name="fuel_end",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="trip",
            name="odometer_start",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="trip",
            name="odometer_end",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
