from rest_framework import serializers

from books.serializers import BookListImageSerializer
from .models import Conversation, ConversationMember, Message


class ConversationUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source='full_name')


class ConversationBookSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=19, decimal_places=4)
    status = serializers.SerializerMethodField()
    images = BookListImageSerializer(many=True, read_only=True)

    @staticmethod
    def get_status(book):
        return {
            'AVAILABLE': 'available',
            'RESERVED': 'reserved',
            'ON_LOAN': 'available',
            'SOLD': 'sold',
            'UNAVAILABLE': 'hidden',
        }.get(book.status, book.status.lower())


class ConversationSerializer(serializers.ModelSerializer):
    book = serializers.SerializerMethodField()
    buyer = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'book', 'buyer', 'seller', 'created_at', 'updated_at')

    @staticmethod
    def _members(conversation):
        members = getattr(conversation, '_prefetched_objects_cache', {}).get('members')
        if members is None:
            members = list(
                ConversationMember.objects
                .filter(conversation=conversation)
                .select_related('user')
                .order_by('joined_at', 'user_id')[:2]
            )
        return members

    def get_book(self, conversation):
        book = getattr(conversation, 'book_context', None)
        if book is None:
            return None
        return ConversationBookSerializer(book).data

    def get_buyer(self, conversation):
        members = self._members(conversation)
        return ConversationUserSerializer(members[0].user).data if members else None

    def get_seller(self, conversation):
        members = self._members(conversation)
        return ConversationUserSerializer(members[1].user).data if len(members) > 1 else None


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    created_at = serializers.DateTimeField(source='sent_at', read_only=True)
    is_read = serializers.SerializerMethodField()
    content = serializers.CharField(max_length=5000, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = Message
        fields = ('id', 'sender_id', 'content', 'is_read', 'created_at')
        read_only_fields = ('id', 'sender_id', 'is_read', 'created_at')

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Nội dung tin nhắn không được để trống.')
        return value

    def get_is_read(self, message):
        reader_last_read_at = getattr(message, 'reader_last_read_at', None)
        return reader_last_read_at is not None and message.sent_at <= reader_last_read_at
