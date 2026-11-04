import uuid

from django.core.validators import FileExtensionValidator
from django.db import migrations, models


def populate_card_ids(apps, schema_editor):
    user_model = apps.get_model("accounts", "User")
    for user in user_model.objects.filter(card_id__isnull=True).iterator():
        user.card_id = uuid.uuid4()
        user.save(update_fields=["card_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_identification_document_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="card_id",
            field=models.UUIDField(
                editable=False,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_photos/",
                validators=[
                    FileExtensionValidator(["jpg", "jpeg", "png", "webp"])
                ],
            ),
        ),
        migrations.RunPython(
            populate_card_ids,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="user",
            name="card_id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
