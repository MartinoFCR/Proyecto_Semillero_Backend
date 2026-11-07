from rest_framework import serializers

from .models import SupportRequest


class SupportRequestSerializer(serializers.ModelSerializer):
    reference = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    customer_telephone = serializers.CharField(source="customer.telephone", read_only=True)
    sale_code = serializers.SerializerMethodField()

    class Meta:
        model = SupportRequest
        fields = (
            "id",
            "reference",
            "customer",
            "customer_name",
            "customer_email",
            "customer_telephone",
            "category",
            "sale",
            "sale_code",
            "subject",
            "message",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "reference", "customer", "created_at", "updated_at")

    def get_reference(self, obj):
        return f"SOL-{obj.pk:06d}"

    def get_customer_name(self, obj):
        user = obj.customer
        if user:
            full = f"{user.first_name} {user.last_name}".strip()
            return full if full else user.username
        return ""

    def get_sale_code(self, obj):
        if obj.sale:
            return f"VTA-{obj.sale.id:06d}"
        return None

    def validate_status(self, value):
        user = self.context.get("request").user if self.context.get("request") else None
        if user and getattr(user, "role", None) != "admin":
            if self.instance and self.instance.status != value:
                raise serializers.ValidationError("Solo un administrador puede modificar el estado de la solicitud.")
        return value
