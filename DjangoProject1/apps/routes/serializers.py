from rest_framework import serializers

from DjangoProject1.apps.routes.models import Route


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = "__all__"
