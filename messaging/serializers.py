from rest_framework import serializers

from books.serializers import BookImageSerializer
from .models import Conversation, Message


class ConversationUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ConversationBookSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    images = BookImageSerializer(many=True, read_only=True)


class ConversationSerializer(serializers.ModelSerializer):
    book = ConversationBookSerializer(read_only=True)
    buyer = ConversationUserSerializer(read_only=True)
    seller = ConversationUserSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ('id', 'book', 'buyer', 'seller', 'created_at', 'updated_at')


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
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
