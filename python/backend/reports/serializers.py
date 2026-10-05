from rest_framework import serializers

from books.models import Book, LendListing, SaleListing
from messaging.models import ConversationMember, Message
from users.models import User
from .models import Report


REPORT_REASONS = (
    'INAPPROPRIATE_CONTENT',
    'INCORRECT_BOOK_INFO',
    'SPAM',
    'SCAM',
    'POLICY_VIOLATION',
    'OTHER',
)


class ReportSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(source='book.id', read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'id', 'book_id', 'reported_user_id', 'sale_listing_id',
            'lend_listing_id', 'message_id', 'reason', 'description', 'status',
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
    reason = serializers.ChoiceField(choices=REPORT_REASONS)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)

    def validate(self, attrs):
        targets = ('reported_user', 'book', 'sale_listing', 'lend_listing', 'message')
        target_count = sum(attrs.get(target) is not None for target in targets)
        if target_count != 1:
            raise serializers.ValidationError(
                'Báo cáo phải xác định chính xác một đối tượng.',
            )
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return attrs

        reporter_id = request.user.id
        reported_user = attrs.get('reported_user')
        sale_listing = attrs.get('sale_listing')
        lend_listing = attrs.get('lend_listing')
        message = attrs.get('message')
        if reported_user is not None and reported_user.id == reporter_id:
            raise serializers.ValidationError({
                'reported_user_id': 'Không thể báo cáo chính tài khoản của bạn.',
            })
        if sale_listing is not None and sale_listing.seller_id == reporter_id:
            raise serializers.ValidationError({
                'sale_listing_id': 'Không thể báo cáo tin đăng của chính bạn.',
            })
        if lend_listing is not None and lend_listing.lender_id == reporter_id:
            raise serializers.ValidationError({
                'lend_listing_id': 'Không thể báo cáo tin đăng của chính bạn.',
            })
        if message is not None:
            if message.sender_id == reporter_id:
                raise serializers.ValidationError({
                    'message_id': 'Không thể báo cáo tin nhắn do chính bạn gửi.',
                })
            is_conversation_member = ConversationMember.objects.filter(
                conversation_id=message.conversation_id,
                user_id=reporter_id,
            ).exists()
            if not is_conversation_member:
                raise serializers.ValidationError({
                    'message_id': 'Bạn không có quyền báo cáo tin nhắn này.',
                })
        return attrs
