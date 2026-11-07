from rest_framework import serializers

from DjangoProject1.apps.routes.models import Route


class RouteSerializer(serializers.ModelSerializer):
    origin_name = serializers.CharField(source="origin.place_name", read_only=True)
    destination_name = serializers.CharField(source="destination.place_name", read_only=True)
    origin_city = serializers.CharField(source="origin.city.city_name", read_only=True)
    destination_city = serializers.CharField(source="destination.city.city_name", read_only=True)

    class Meta:
        model = Route
        fields = (
            "id",
            "origin",
            "destination",
            "origin_name",
            "destination_name",
            "origin_city",
            "destination_city",
            "distance_km",
        )

    def validate_distance_km(self, value):
        if value <= 0:
            raise serializers.ValidationError("La distancia de la ruta debe ser mayor a 0 km.")
        return value

    def validate(self, attrs):
        instance = self.instance
        origin = attrs.get("origin", instance.origin if instance else None)
        destination = attrs.get("destination", instance.destination if instance else None)

        if origin and destination and origin == destination:
            raise serializers.ValidationError({
                "destination": "El origen y el destino de la ruta no pueden ser la misma ubicación."
            })

        if origin and destination:
            qs = Route.objects.filter(origin=origin, destination=destination)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "non_field_errors": [
                        f"Ya existe una ruta registrada desde '{origin.place_name}' hasta '{destination.place_name}'."
                    ]
                })

        return attrs
