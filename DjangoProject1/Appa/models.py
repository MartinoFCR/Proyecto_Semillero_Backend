from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.contrib.gis.db import models

# Create your models here.

class Buses(models.Model):
    id_bus = models.AutoField(primary_key=True)
    plate = models.CharField(max_length=10, null=False, unique=True)
    capacity = models.IntegerField()
    model = models.CharField(max_length=50)
    state = models.CharField(max_length=20, default='Active')

    class Meta:
        ordering = ['id_bus']

class Drivers(models.Model):
    id_driver = models.AutoField(primary_key=True)
    driver_name = models.CharField(max_length=100, null=False)
    licence = models.CharField(max_length=20, null=False, unique=True)
    fullname = models.CharField(max_length=50, null=False)
    address = models.CharField(max_length=50, null=False)
    phone_number = models.CharField(max_length=20, null=False)

class Departments(models.Model):
    id_department = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=100, null=False)

class Cities(models.Model):
    id_city = models.AutoField(primary_key=True)
    city_name = models.CharField(max_length=100, null=False)

class Places(models.Model):
    id_place = models.AutoField(primary_key=True)
    place_name = models.CharField(max_length=50, null=False)
    place_city = models.ForeignKey(Cities, on_delete=models.CASCADE, null=False)
    place_department = models.ForeignKey(Departments, on_delete=models.CASCADE, null=False)
    place_point = models.PointField(srid=4326)

class Routes(models.Model):
    id_route = models.AutoField(primary_key=True)
    origin = models.ForeignKey(Places, on_delete=models.CASCADE, related_name='origin_route', null=False)
    destination = models.ForeignKey(Places, on_delete=models.CASCADE, related_name='destination_route', null=False)
    distance_km = models.IntegerField()

class Trips(models.Model):
    id_trip = models.AutoField(primary_key=True)
    id_bus = models.ForeignKey(Buses, on_delete=models.CASCADE, null=False)
    id_driver = models.ForeignKey(Drivers, on_delete=models.CASCADE, null=False)
    id_route = models.ForeignKey(Routes, on_delete=models.CASCADE, null=False)
    date_time_start = models.DateTimeField(default=timezone.now)
    date_time_end = models.DateTimeField()
    fuel_start = models.IntegerField()
    fuel_end = models.IntegerField()
    odometer_start = models.IntegerField()
    odometer_end = models.IntegerField()
    passengers_start = models.IntegerField(default=0)
    trip_state = models.CharField(max_length=20, default='En curso')

class Readings(models.Model):
    id_reading = models.AutoField(primary_key=True)
    id_trip = models.ForeignKey(Trips, on_delete=models.CASCADE, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    speed = models.IntegerField()
    fuel_level = models.IntegerField()
    reading_point = models.PointField(srid=4326)

class Seats(models.Model):
    id_seat = models.AutoField(primary_key=True)
    id_bus = models.ForeignKey(Buses, on_delete=models.CASCADE, null=False)
    seat_number = models.CharField(max_length=5, null=False)
    row = models.CharField(max_length=5, null=False)
    col = models.CharField(max_length=5, null=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['id_bus', 'seat_number'],
                name='unique_bus_seat_number'
            )
        ]
    def __str__(self):
        return f'Asiento {self.seat_number} - Bus {self.id_bus}'

class SeatsState(models.Model):
    id_state = models.AutoField(primary_key=True)
    id_trip = models.ForeignKey(Trips, on_delete=models.CASCADE, null=False)
    id_seat = models.ForeignKey(Seats, on_delete=models.CASCADE, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    occupied = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['id_trip', 'id_seat'],
                name='unique_seat_actual_state'
            )
        ]
class SeatsStateRecord(models.Model):
    id_record = models.AutoField(primary_key=True)
    id_trip = models.ForeignKey(Trips, on_delete=models.CASCADE, null=False)
    id_seat = models.ForeignKey(Seats, on_delete=models.CASCADE, null=False)
    time_stamp = models.DateTimeField(default=timezone.now)
    occupied = models.BooleanField(default=False)

class Events(models.Model):
    id_event = models.AutoField(primary_key=True)
    id_trip = models.ForeignKey(Trips, on_delete=models.CASCADE, null=False)
    event_time_stamp = models.DateTimeField(default=timezone.now)
    event_point = models.PointField(srid=4326)
    event_type = models.CharField(max_length=50, null=False)
    description = models.TextField()

class Users(AbstractUser):
    id_user = models.AutoField(primary_key=True)
    username = models.CharField(max_length=30, null=False, unique=True)
    email = models.EmailField(max_length=50, unique=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    identification_number = models.CharField(max_length=20, unique=True)

    ROL_CHOICES = (
        ('client', 'Cliente'),
        ('driver', 'Conductor'),
        ('admin', 'Administrador'),
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='client')

    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['identification_number']

    def __str__(self):
        return f"{self.username} ({self.rol})"