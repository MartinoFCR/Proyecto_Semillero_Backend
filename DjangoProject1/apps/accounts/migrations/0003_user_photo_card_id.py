import uuid

from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_identification_document_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="card_id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
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
    ]
