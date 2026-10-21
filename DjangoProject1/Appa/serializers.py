from rest_framework import serializers

from DjangoProject1.Appa.models import User, Trip


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User

class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip