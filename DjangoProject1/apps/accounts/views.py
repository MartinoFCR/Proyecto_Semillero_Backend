from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated

from DjangoProject1.apps.accounts.models import User
from DjangoProject1.apps.accounts.serializers import (
    CustomerSerializer,
    ProfileSerializer,
    PublicRegistrationSerializer,
    UserSerializer,
)
from DjangoProject1.permissions import IsAdminRole


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save()


class CustomerSearchView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        identification_number = request.query_params.get(
            "identification_number",
            "",
        ).strip()
        if not identification_number:
            return Response(
                {"identification_number": "Este parámetro es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = User.objects.filter(
            role=User.Role.CLIENT,
            identification_number__iexact=identification_number,
        ).first()
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CustomerSerializer(customer).data)


class CustomerListCreateView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        customers = User.objects.filter(
            role=User.Role.CLIENT
        ).order_by("id")
        return Response(CustomerSerializer(customers, many=True).data)

    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return Response(
            CustomerSerializer(customer).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get_object(self, pk):
        return User.objects.filter(
            pk=pk,
            role=User.Role.CLIENT,
        ).first()

    def get(self, request, pk):
        customer = self.get_object(pk)
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CustomerSerializer(customer).data)

    def patch(self, request, pk):
        customer = self.get_object(pk)
        if customer is None:
            return Response(
                {"detail": "Cliente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CustomerSerializer(
            customer,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(CustomerSerializer(serializer.save()).data)


class PublicRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PublicRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            ProfileSerializer(serializer.save()).data,
            status=status.HTTP_201_CREATED,
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(ProfileSerializer(serializer.save()).data)
