from django.test import TestCase
from rest_framework.exceptions import ValidationError

from DjangoProject1.apps.fleet.models import Bus, BusType
from DjangoProject1.apps.fleet.serializers import BusSerializer


class BusTypeTests(TestCase):
    def setUp(self):
        self.bus_type = BusType.objects.create(
            name="Bus urbano",
            code="bus-urbano",
            max_capacity=60,
        )

    def test_bus_capacity_cannot_exceed_type_capacity(self):
        serializer = BusSerializer(data={
            "plate": "ABC123",
            "capacity": 61,
            "model": "2024",
            "bus_type": self.bus_type.id,
            "state": Bus.State.ACTIVE,
        })

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_bus_type_is_optional_for_existing_bus_compatibility(self):
        bus = Bus.objects.create(
            plate="DEF456",
            capacity=40,
            model="2024",
        )

        self.assertIsNone(bus.bus_type)
