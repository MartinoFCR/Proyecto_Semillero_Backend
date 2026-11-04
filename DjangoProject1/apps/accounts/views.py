from django.core import signing
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from django.core import signing
from django.core.files.images import get_image_dimensions
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
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
        return Response(
            ProfileSerializer(
                request.user,
                context={"request": request},
            ).data
        )

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(
            ProfileSerializer(
                serializer.save(),
                context={"request": request},
            ).data
        )


class ProfilePhotoView(APIView):
    permission_classes = [IsAuthenticated]
    max_size = 5 * 1024 * 1024
    max_dimension = 2000

    def post(self, request):
        photo = request.FILES.get("photo")
        if not photo:
            return Response(
                {"photo": "El archivo photo es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if photo.size > self.max_size:
            return Response(
                {"photo": "La imagen no puede superar 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            photo.seek(0)
            image = Image.open(photo)
            image_format = image.format
            width, height = image.size
            image.verify()
            photo.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            return Response(
                {"photo": "El archivo no es una imagen válida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_format not in {"JPEG", "PNG", "WEBP"}:
            return Response(
                {"photo": "Solo se admiten JPG, PNG y WEBP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if width > self.max_dimension or height > self.max_dimension:
            return Response(
                {"photo": "Las dimensiones máximas son 2000 x 2000 píxeles."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_photo = request.user.photo
        request.user.photo = photo
        request.user.save(update_fields=["photo"])
        if old_photo and old_photo.name != request.user.photo.name:
            old_photo.delete(save=False)
        return Response(
            ProfileSerializer(
                request.user,
                context={"request": request},
            ).data
        )

    def delete(self, request):
        if request.user.photo:
            photo = request.user.photo
            request.user.photo = None
            request.user.save(update_fields=["photo"])
            photo.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DigitalCardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = signing.TimestampSigner(
            salt="client-card",
        ).sign(str(request.user.card_id))
        verification_url = request.build_absolute_uri(
            reverse("card-verify"),
        )
        return Response({
            "name": (
                f"{request.user.first_name} {request.user.last_name}"
            ).strip(),
            "card_id": str(request.user.card_id),
            "photo_url": ProfileSerializer(
                request.user,
                context={"request": request},
            ).data["photo_url"],
            "status": "active" if request.user.is_active else "revoked",
            "valid_until": None,
            "qr": {
                "token": token,
                "verification_url": verification_url,
            },
            "warning": "Este carné no sustituye un tiquete ni acredita una compra.",
        })


class CardVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "")
        try:
            card_id = signing.TimestampSigner(
                salt="client-card",
            ).unsign(token, max_age=365 * 24 * 60 * 60)
            user = User.objects.get(card_id=card_id)
        except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
            return Response(
                {"valid": False, "detail": "El carné no es válido."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            "valid": user.is_active,
            "card_id": str(user.card_id),
            "name": f"{user.first_name} {user.last_name}".strip(),
            "status": "active" if user.is_active else "revoked",
            "valid_until": None,
        })
