from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='notification_type', read_only=True)
    reference_id = serializers.IntegerField(source='entity_id', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = (
            'id', 'type', 'title', 'content', 'reference_id',
            'is_read', 'created_at',
        )
        read_only_fields = fields
