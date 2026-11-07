from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from DjangoProject1.apps.geography.models import City, Department, Place
from DjangoProject1.apps.routes.models import Route
from DjangoProject1.apps.routes.serializers import RouteSerializer


class RouteValidationTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(department_name="Antioquia")
        self.city_med = City.objects.create(city_name="Medellín", department=self.dept)
        self.city_bog = City.objects.create(city_name="Bogotá", department=self.dept)

        self.place_med = Place.objects.create(
            place_name="Terminal Norte",
            city=self.city_med,
            place_point=Point(-75.57, 6.28),
        )
        self.place_bog = Place.objects.create(
            place_name="Terminal Salitre",
            city=self.city_bog,
            place_point=Point(-74.11, 4.65),
        )

    def test_same_origin_and_destination_fails(self):
        data = {
            "origin": self.place_med.id,
            "destination": self.place_med.id,
            "distance_km": 100,
        }
        serializer = RouteSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("destination", serializer.errors)

    def test_zero_or_negative_distance_fails(self):
        data = {
            "origin": self.place_med.id,
            "destination": self.place_bog.id,
            "distance_km": 0,
        }
        serializer = RouteSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("distance_km", serializer.errors)

    def test_duplicate_route_fails(self):
        Route.objects.create(
            origin=self.place_med,
            destination=self.place_bog,
            distance_km=420,
        )

        data = {
            "origin": self.place_med.id,
            "destination": self.place_bog.id,
            "distance_km": 430,
        }
        serializer = RouteSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_valid_route_and_read_only_names(self):
        data = {
            "origin": self.place_med.id,
            "destination": self.place_bog.id,
            "distance_km": 420.5,
        }
        serializer = RouteSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        route = serializer.save()
        self.assertEqual(serializer.data["origin_name"], "Terminal Norte")
        self.assertEqual(serializer.data["destination_name"], "Terminal Salitre")
        self.assertEqual(serializer.data["origin_city"], "Medellín")
        self.assertEqual(serializer.data["destination_city"], "Bogotá")
