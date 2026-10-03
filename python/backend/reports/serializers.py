from rest_framework import serializers

from books.models import Book, LendListing, SaleListing
from messaging.models import Message
from users.models import User
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(source='book.id', read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'id', 'book_id', 'reason', 'description', 'status',
            'created_at', 'resolved_at',
        )
        read_only_fields = fields

    @staticmethod
    def get_status(report):
        return {
            'OPEN': 'pending',
            'IN_REVIEW': 'reviewing',
            'RESOLVED': 'resolved',
            'REJECTED': 'rejected',
        }.get(report.status, report.status.lower())


class ReportCreateSerializer(serializers.Serializer):
    book_id = serializers.PrimaryKeyRelatedField(
        source='book', queryset=Book.objects.all(), required=False, allow_null=True,
    )
    reported_user_id = serializers.PrimaryKeyRelatedField(
        source='reported_user', queryset=User.objects.all(),
        required=False, allow_null=True,
    )
    sale_listing_id = serializers.PrimaryKeyRelatedField(
        source='sale_listing', queryset=SaleListing.objects.all(), required=False, allow_null=True,
    )
    lend_listing_id = serializers.PrimaryKeyRelatedField(
        source='lend_listing', queryset=LendListing.objects.all(), required=False, allow_null=True,
    )
    message_id = serializers.PrimaryKeyRelatedField(
        source='message', queryset=Message.objects.all(), required=False, allow_null=True,
    )
    reason = serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Lý do không được để trống.')
        return value

    def validate(self, attrs):
        targets = ('reported_user', 'book', 'sale_listing', 'lend_listing', 'message')
        target_count = sum(attrs.get(target) is not None for target in targets)
        if target_count != 1:
            raise serializers.ValidationError(
                'Báo cáo phải xác định chính xác một đối tượng.',
            )
        return attrs
