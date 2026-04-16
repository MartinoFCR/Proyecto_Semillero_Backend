from rest_framework import serializers

from DjangoProject1.Appa.models import Users, Trips


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users

class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trips