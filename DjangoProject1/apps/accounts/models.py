from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
import uuid
from django.utils import timezone


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
    password_changed_at = models.DateTimeField(default=timezone.now)
    password_change_required = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['identification_number']

    class Meta:
        verbose_name_plural = 'Usuarios'
        verbose_name = 'Usuario'
    def __str__(self):
        return f"{self.username} ({self.role})"


class AccountActionToken(models.Model):
    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Recuperación"
        ACTIVATION = "activation", "Activación"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="action_tokens")
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("user", "purpose", "created_at")),
        ]


class LoginAttempt(models.Model):
    key = models.CharField(max_length=255, unique=True)
    window_started_at = models.DateTimeField()
    failures = models.PositiveSmallIntegerField(default=0)