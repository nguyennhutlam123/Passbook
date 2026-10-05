from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(source='book.id', read_only=True, allow_null=True)

    class Meta:
        model = Report
        fields = ('id', 'book_id', 'reason', 'description', 'status', 'created_at', 'resolved_at')
        read_only_fields = ('id', 'status', 'created_at', 'resolved_at')


class ReportCreateSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(max_length=5000, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = Report
        fields = ('book_id', 'reason', 'description')

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Lý do không được để trống.')
        return value

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Mô tả không được để trống.')
        return value
