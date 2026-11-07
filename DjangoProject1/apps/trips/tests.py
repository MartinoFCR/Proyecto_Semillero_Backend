from datetime import timedelta
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from DjangoProject1.apps.fleet.models import Bus, Driver
from DjangoProject1.apps.geography.models import City, Department, Place
from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.trips.models import Trip, TripFare
from DjangoProject1.apps.trips.serializers import TripSerializer


class TripValidationAndScheduleTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(department_name="Valle")
        self.city_cali = City.objects.create(city_name="Cali", department=self.dept)
        self.city_bog = City.objects.create(city_name="Bogotá", department=self.dept)

        self.place_cali = Place.objects.create(
            place_name="Terminal Cali",
            city=self.city_cali,
            place_point=Point(-76.53, 3.45),
        )
        self.place_bog = Place.objects.create(
            place_name="Terminal Salitre",
            city=self.city_bog,
            place_point=Point(-74.11, 4.65),
        )

        self.route = Route.objects.create(
            origin=self.place_cali,
            destination=self.place_bog,
            distance_km=480,
        )

        self.bus_active = Bus.objects.create(
            plate="BUS-ACT-01",
            capacity=30,
            model="2024",
            state=Bus.State.ACTIVE,
        )
        self.bus_maint = Bus.objects.create(
            plate="BUS-MNT-02",
            capacity=30,
            model="2022",
            state=Bus.State.MAINTENANCE,
        )

        self.driver_active = Driver.objects.create(
            full_name="Driver Operativo 1",
            license_number="LIC-OP-10",
            address="Calle 10",
            phone_number="3000000010",
            is_active=True,
        )
        self.driver_inactive = Driver.objects.create(
            full_name="Driver Inactivo 2",
            license_number="LIC-INACT-20",
            address="Calle 20",
            phone_number="3000000020",
            is_active=False,
        )

    def test_assign_inactive_bus_fails(self):
        now = timezone.now()
        data = {
            "bus": self.bus_maint.id,
            "driver": self.driver_active.id,
            "route": self.route.id,
            "date_time_start": now,
            "date_time_end": now + timedelta(hours=5),
        }
        serializer = TripSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bus", serializer.errors)

    def test_assign_inactive_driver_fails(self):
        now = timezone.now()
        data = {
            "bus": self.bus_active.id,
            "driver": self.driver_inactive.id,
            "route": self.route.id,
            "date_time_start": now,
            "date_time_end": now + timedelta(hours=5),
        }
        serializer = TripSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("driver", serializer.errors)

    def test_bus_schedule_overlap_fails(self):
        now = timezone.now()
        start_time = now + timedelta(days=1)
        end_time = start_time + timedelta(hours=8)

        # Crear primer viaje
        Trip.objects.create(
            bus=self.bus_active,
            driver=self.driver_active,
            route=self.route,
            date_time_start=start_time,
            date_time_end=end_time,
            trip_state=Trip.TripState.SCHEDULED,
        )

        # Otro conductor para aislar la validación al bus
        other_driver = Driver.objects.create(
            full_name="Driver Operativo 2",
            license_number="LIC-OP-99",
            address="Calle 99",
            phone_number="3000000099",
            is_active=True,
        )

        # Intentar programar el mismo bus en horario solapado (1 hora después del inicio)
        overlap_data = {
            "bus": self.bus_active.id,
            "driver": other_driver.id,
            "route": self.route.id,
            "date_time_start": start_time + timedelta(hours=1),
            "date_time_end": end_time + timedelta(hours=2),
        }
        serializer = TripSerializer(data=overlap_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bus", serializer.errors)

    def test_create_trip_with_embedded_fare_amount_cents(self):
        now = timezone.now()
        data = {
            "bus": self.bus_active.id,
            "driver": self.driver_active.id,
            "route": self.route.id,
            "date_time_start": now + timedelta(days=2),
            "date_time_end": now + timedelta(days=2, hours=6),
            "fare_amount_cents": 7500000,  # $75.000 COP
        }
        serializer = TripSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        trip = serializer.save()

        # Verificar que la tarifa se creó automáticamente
        fare = TripFare.objects.get(trip=trip)
        self.assertEqual(fare.amount_cents, 7500000)
        self.assertEqual(serializer.data["fare_amount_cents"], 7500000)
        self.assertEqual(serializer.data["bus_plate"], "BUS-ACT-01")
        self.assertEqual(serializer.data["driver_name"], "Driver Operativo 1")

    def test_telemetry_ingest_updates_reading_and_seats(self):
        from DjangoProject1.apps.fleet.models import GPSDevice, Seat
        from DjangoProject1.apps.trips.models import CurrentSeatState, Reading, SeatsStateRecord
        from DjangoProject1.apps.trips.telemetry_services import ingest_device_telemetry

        # Crear viaje en progreso
        trip = Trip.objects.create(
            bus=self.bus_active,
            driver=self.driver_active,
            route=self.route,
            date_time_start=timezone.now(),
            trip_state=Trip.TripState.IN_PROGRESS,
        )

        # Crear sillas 1 y 2 en el bus
        seat_1 = Seat.objects.create(bus=self.bus_active, seat_number="1", row="1", col="1")
        seat_2 = Seat.objects.create(bus=self.bus_active, seat_number="2", row="1", col="2")

        # Crear y asignar dispositivo GPS
        device = GPSDevice.objects.create(
            name="ESP32-Ruta-Valle",
            device_id="ESP32_TELEMETRY_01",
            bus=self.bus_active,
            state=GPSDevice.State.ACTIVE,
        )

        payload = {
            "device_id": "ESP32_TELEMETRY_01",
            "timestamp": "2026-11-06T22:00:00Z",
            "gps": {
                "lat": 3.4516,
                "lng": -76.5320,
                "speed": 62.5,
                "fuel_level": 80.0,
            },
            "seats": [
                {"seat": "1", "occupied": True},
                {"seat": "2", "occupied": False},
            ],
        }

        result = ingest_device_telemetry(payload)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["active_trip_id"], trip.id)
        self.assertEqual(result["readings_created"], 1)

        # Verificar Reading creado
        reading = Reading.objects.filter(trip=trip).first()
        self.assertIsNotNone(reading)
        self.assertEqual(reading.speed, 62.5)
        self.assertEqual(reading.fuel_level, 80.0)

        # Verificar CurrentSeatState
        state_1 = CurrentSeatState.objects.get(trip=trip, seat=seat_1)
        state_2 = CurrentSeatState.objects.get(trip=trip, seat=seat_2)
        self.assertTrue(state_1.occupied)
        self.assertFalse(state_2.occupied)

        # Verificar que el ping del dispositivo se actualizó
        device.refresh_from_db()
        self.assertIsNotNone(device.last_ping_at)
