from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0009_gpsdevice_api_key_hash"),
    ]

    operations = [
        migrations.AlterField(
            model_name="driver",
            name="full_name",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="driver",
            name="license_number",
            field=models.CharField(max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name="driver",
            name="address",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="driver",
            name="phone_number",
            field=models.CharField(max_length=30),
        ),
        migrations.AddField(
            model_name="driver",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="driver",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="driver",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("CC", "CC"),
                    ("DNI", "DNI"),
                    ("PASSPORT", "PASSPORT"),
                    ("CE", "CE"),
                ],
                default="CC",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="document_number",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="driver",
            name="birth_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="driver",
            name="license_category",
            field=models.CharField(
                choices=[("C1", "C1"), ("C2", "C2"), ("C3", "C3")],
                default="C3",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="license_expiry",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="experience_years",
            field=models.PositiveSmallIntegerField(default=4),
        ),
        migrations.AddField(
            model_name="driver",
            name="blood_group",
            field=models.CharField(
                choices=[
                    ("O+", "O+"),
                    ("O-", "O-"),
                    ("A+", "A+"),
                    ("A-", "A-"),
                    ("B+", "B+"),
                    ("B-", "B-"),
                    ("AB+", "AB+"),
                    ("AB-", "AB-"),
                ],
                default="O+",
                max_length=5,
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="operational_status",
            field=models.CharField(
                choices=[
                    ("DISPONIBLE", "Disponible"),
                    ("ACTIVO", "Activo en Flota"),
                    ("CAPACITACION", "En Capacitación"),
                ],
                default="DISPONIBLE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="photo",
            field=models.ImageField(
                blank=True, null=True, upload_to="driver_photos/"
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="has_medical_exam",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="has_psychosensometric_test",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="has_clean_driving_record",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="has_first_aid_training",
            field=models.BooleanField(default=False),
        ),
    ]
