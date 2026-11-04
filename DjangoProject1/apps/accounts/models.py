from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
import uuid


# Create your models here.
class User(AbstractUser):
    email = models.EmailField(max_length=50, unique=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(
        upload_to="profile_photos/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    card_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class DocumentType(models.TextChoices):
        CC = "13", "Cédula de ciudadanía"
        CE = "22", "Cédula de extranjería"
        PASSPORT = "41", "Pasaporte"
        TI = "12", "Tarjeta de identidad"

    identification_document_code = models.CharField(
        max_length=2,
        choices=DocumentType.choices,
        blank=True,
        default="",
    )
    identification_number = models.CharField(max_length=20, unique=True)
    
    class Role(models.TextChoices):
        CLIENT = 'client', 'Cliente'
        DRIVER = 'driver', 'Conductor'
        ADMIN = 'admin', 'Administrador'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['identification_number']

    class Meta:
        verbose_name_plural = 'Usuarios'
        verbose_name = 'Usuario'
    def __str__(self):
        return f"{self.username} ({self.role})"