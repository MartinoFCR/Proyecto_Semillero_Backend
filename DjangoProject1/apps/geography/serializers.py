from rest_framework import serializers

from DjangoProject1.apps.geography.models import City, Department, Place
from DjangoProject1.serializers import GeoJSONPointField


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = "__all__"


class PlaceSerializer(serializers.ModelSerializer):
    place_point = GeoJSONPointField()

    class Meta:
        model = Place
        fields = "__all__"
