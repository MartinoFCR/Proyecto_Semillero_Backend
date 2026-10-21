from django.db import models
from django.conf import settings

# Create your models here.
class Bus(models.Model):
    class State(models.TextChoices):
        ACTIVE = 'Active', 'Activo'
        INACTIVE = 'Inactive', 'Inactivo'
        MAINTENANCE = 'Maintenance', 'Mantenimiento'
        
    plate = models.CharField(max_length=10, null=False, unique=True)
    capacity = models.IntegerField()
    model = models.CharField(max_length=50)
    state = models.CharField(max_length=20, choices=State.choices, default=State.ACTIVE)

    class Meta:
        verbose_name_plural = 'Buses'
        verbose_name = 'Bus'
        ordering = ['id']

class Driver(models.Model):
    full_name = models.CharField(max_length=70, null=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='driver_profile'
    )
    license_number = models.CharField(max_length=20, null=False, unique=True)
    address = models.CharField(max_length=50, null=False)
    phone_number = models.CharField(max_length=20, null=False)

    class Meta:
        verbose_name_plural = 'Conductores'
        verbose_name = 'Conductor'

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

