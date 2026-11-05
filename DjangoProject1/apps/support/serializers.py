from rest_framework import serializers

from .models import SupportRequest


class SupportRequestSerializer(serializers.ModelSerializer):
    reference = serializers.SerializerMethodField()

    class Meta:
        model = SupportRequest
        fields = (
            "id",
            "reference",
            "category",
            "sale",
            "subject",
            "message",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "reference", "status", "created_at", "updated_at")

    def get_reference(self, obj):
        return f"SOL-{obj.pk:06d}"
