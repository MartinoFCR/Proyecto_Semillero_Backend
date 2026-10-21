
from rest_framework import generics
from rest_framework.permissions import IsAdminUser

from DjangoProject1.Appa.models import User
from django.contrib.auth.models import Group
from rest_framework import permissions, viewsets


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all().order_by("-date_joined")
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Group.objects.all().order_by("name")
    permission_classes = [permissions.IsAuthenticated]