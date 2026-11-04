import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0003_alter_bus_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=80, unique=True)),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("max_capacity", models.PositiveIntegerField()),
            ],
            options={
                "verbose_name": "Tipo de bus",
                "verbose_name_plural": "Tipos de bus",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="bus",
            name="bus_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="buses",
                to="fleet.bustype",
            ),
        ),
    ]
