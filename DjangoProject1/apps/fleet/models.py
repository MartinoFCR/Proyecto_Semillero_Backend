from django.db import models
from django.conf import settings

# Create your models here.
class BusType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    max_capacity = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Tipo de bus"
        verbose_name_plural = "Tipos de bus"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Bus(models.Model):
    class State(models.TextChoices):
        ACTIVE = 'Active', 'Activo'
        INACTIVE = 'Inactive', 'Inactivo'
        MAINTENANCE = 'Maintenance', 'Mantenimiento'
        
    plate = models.CharField(max_length=10, null=False, unique=True)
    capacity = models.IntegerField()
    model = models.CharField(max_length=50)
    bus_type = models.ForeignKey(
        BusType,
        on_delete=models.PROTECT,
        related_name="buses",
        null=True,
        blank=True,
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.ACTIVE)

    class Meta:
        verbose_name_plural = 'Buses'
        verbose_name = 'Bus'
        ordering = ['id']

class Driver(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("CC", "CC"),
        ("DNI", "DNI"),
        ("PASSPORT", "PASSPORT"),
        ("CE", "CE"),
    ]
    LICENSE_CATEGORY_CHOICES = [
        ("C1", "C1"),
        ("C2", "C2"),
        ("C3", "C3"),
    ]
    BLOOD_GROUP_CHOICES = [
        ("O+", "O+"),
        ("O-", "O-"),
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
    ]
    OPERATIONAL_STATUS_CHOICES = [
        ("DISPONIBLE", "Disponible"),
        ("ACTIVO", "Activo en Flota"),
        ("CAPACITACION", "En Capacitación"),
    ]

    full_name = models.CharField(max_length=150, null=False)
    first_name = models.CharField(max_length=120, blank=True, default="")
    last_name = models.CharField(max_length=120, blank=True, default="")
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default="CC",
    )
    document_number = models.CharField(max_length=30, blank=True, default="")
    birth_date = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, default="")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_profile'
    )
    license_number = models.CharField(max_length=30, null=False, unique=True)
    license_category = models.CharField(
        max_length=10,
        choices=LICENSE_CATEGORY_CHOICES,
        default="C3",
    )
    license_expiry = models.DateField(null=True, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=4)
    blood_group = models.CharField(
        max_length=5,
        choices=BLOOD_GROUP_CHOICES,
        default="O+",
    )
    operational_status = models.CharField(
        max_length=20,
        choices=OPERATIONAL_STATUS_CHOICES,
        default="DISPONIBLE",
    )
    photo = models.ImageField(
        upload_to="driver_photos/",
        null=True,
        blank=True,
    )
    address = models.CharField(max_length=120, null=False)
    phone_number = models.CharField(max_length=30, null=False)
    is_active = models.BooleanField(default=True)
    has_medical_exam = models.BooleanField(default=True)
    has_psychosensometric_test = models.BooleanField(default=True)
    has_clean_driving_record = models.BooleanField(default=True)
    has_first_aid_training = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Conductores'
        verbose_name = 'Conductor'


class GPSDevice(models.Model):
    class State(models.TextChoices):
        ACTIVE = 'active', 'Activo'
        INACTIVE = 'inactive', 'Inactivo'
        MAINTENANCE = 'maintenance', 'En mantenimiento'

    name = models.CharField(max_length=80, help_text="Nombre o alias identificador del dispositivo (ej. ESP32-Bus-01).")
    device_id = models.CharField(max_length=60, unique=True, help_text="Identificador único del microcontrolador (ej. MAC o ID MQTT).")
    model = models.CharField(max_length=60, blank=True, default="ESP32", help_text="Modelo de placa o microcontrolador.")
    state = models.CharField(max_length=20, choices=State.choices, default=State.ACTIVE)
    api_key_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Hash seguro (PBKDF2/SHA256) de la clave o token del dispositivo.",
    )
    api_key_prefix = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Prefijo visible del token (ej. 'esp_live_a1b2...') para que el usuario identifique cuál clave tiene.",
    )
    bus = models.OneToOneField(
        Bus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gps_device",
        help_text="Bus al que está asignado actualmente este dispositivo.",
    )
    last_ping_at = models.DateTimeField(null=True, blank=True, help_text="Última fecha y hora en la que reportó señal.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def check_api_key(self, raw_key: str) -> bool:
        """Comprueba de forma segura si la clave en texto plano coincide con el hash almacenado."""
        from django.contrib.auth.hashers import check_password
        if not self.api_key_hash or not raw_key:
            return False
        return check_password(raw_key, self.api_key_hash)

    def set_api_key(self, raw_key: str) -> None:
        """Almacena el hash seguro de la clave y extrae su prefijo visible."""
        from django.contrib.auth.hashers import make_password
        self.api_key_hash = make_password(raw_key)
        self.api_key_prefix = raw_key[:12] + "..." if len(raw_key) > 12 else raw_key

    class Meta:
        verbose_name = 'Dispositivo GPS'
        verbose_name_plural = 'Dispositivos GPS'
        ordering = ['id']

    def __str__(self):
        bus_str = f" (Bus: {self.bus.plate})" if self.bus else " (Disponible)"
        return f"{self.name} - {self.device_id}{bus_str}"


class Seat(models.Model):
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        null=False,
        related_name='seats')
    
    seat_number = models.CharField(max_length=5, null=False)
    row = models.CharField(max_length=5, null=False)
    col = models.CharField(max_length=5, null=False)

    class Meta:
        verbose_name_plural = 'Asientos'
        verbose_name = 'Asiento'
        constraints = [
            models.UniqueConstraint(
                fields=['bus', 'seat_number'],
                name='unique_bus_seat'
            )
        ]
    def __str__(self):
        return f'Asiento {self.seat_number} - Bus {self.bus}'
