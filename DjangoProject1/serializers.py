import json

from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from rest_framework import serializers


class GeoJSONPointField(serializers.Field):
    def to_representation(self, value):
        if value is None:
            return None
        return json.loads(value.geojson)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = json.dumps(data)
        if not isinstance(data, str):
            raise serializers.ValidationError("Se esperaba un punto GeoJSON.")

        try:
            point = GEOSGeometry(data)
        except (GEOSException, TypeError, ValueError) as error:
            raise serializers.ValidationError("El punto GeoJSON no es válido.") from error

        if point.geom_type != "Point":
            raise serializers.ValidationError("La geometría debe ser un punto.")
        if point.srid not in (None, 4326):
            raise serializers.ValidationError("El punto debe usar el sistema de referencia 4326.")

        point.srid = 4326
        return point
