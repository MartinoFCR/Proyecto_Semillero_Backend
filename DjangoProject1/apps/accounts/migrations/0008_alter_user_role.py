from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_user_created_by"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("client", "Cliente"),
                    ("driver", "Conductor"),
                    ("seller", "Vendedor / Taquilla"),
                    ("dispatcher", "Despachador Operativo"),
                    ("auditor", "Auditor / Contabilidad"),
                    ("admin", "Administrador"),
                ],
                default="client",
                max_length=20,
            ),
        ),
    ]
