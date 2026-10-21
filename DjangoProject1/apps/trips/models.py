from django.contrib.gis.db import models
from django.utils import timezone
from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.fleet.models import Bus, Driver, Seat

# Create your models here.
class Trip(models.Model):
    
    class TripState(models.TextChoices):
        SCHEDULED = 'scheduled', 'Programado'
        IN_PROGRESS = 'in_progress', 'En curso'
        COMPLETED = 'completed', 'Finalizado'
        CANCELLED = 'cancelled', 'Cancelado'
    
    bus = models.ForeignKey(Bus, on_delete=models.PROTECT, null=False)
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, null=False)
    route = models.ForeignKey(Route, on_delete=models.PROTECT, null=False)
    date_time_start = models.DateTimeField(default=timezone.now)
    date_time_end = models.DateTimeField(
        null=True,
        blank=True
    )
    fuel_start = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    fuel_end = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    odometer_start = models.IntegerField()
    odometer_end = models.IntegerField()
    passengers_start = models.IntegerField(default=0)
    trip_state = models.CharField(
        max_length=20,
        choices=TripState.choices,
        default=TripState.SCHEDULED
    )
    

    class Meta:
        verbose_name_plural = 'Viajes'
        verbose_name = 'Viaje'

class Reading(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    speed = models.DecimalField(
        max_digits=6,
        decimal_places=2
    )
    fuel_level = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    reading_point = models.PointField(srid=4326)

    class Meta:
        indexes = [
            models.Index(
                fields=['trip', 'time_stamp']
            )
        ]
        verbose_name_plural = 'Lecturas'
        verbose_name = 'Lectura'



class Event(models.Model):
    class EventType(models.TextChoices):
        STOP = 'stop', 'Parada'
        ACCIDENT = 'accident', 'Accidente'
        SPEEDING = 'speeding', 'Exceso de velocidad'
        ROUTE_DEVIATION = 'route_deviation', 'Desviación de ruta'
        EMERGENCY = 'emergency', 'Emergencia'
        
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, null=False)
    event_time_stamp = models.DateTimeField(default=timezone.now)
    event_point = models.PointField(srid=4326)
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices
    )   
    description = models.TextField()
    
    class Meta:
        indexes = [
            models.Index(
                fields=['trip', 'event_time_stamp']
            )
        ]

class CurrentSeatState(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, null=False)
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    occupied = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['trip', 'seat'],
                name='unique_seat_actual_state'
            )
        ]
class SeatsStateRecord(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, null=False)
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    occupied = models.BooleanField(default=False)