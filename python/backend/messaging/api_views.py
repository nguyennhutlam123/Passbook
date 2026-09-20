from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from books.models import Book, BookImage
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


def conversation_queryset():
    return (
        Conversation.objects
        .select_related('book', 'buyer', 'seller')
        .prefetch_related(
            Prefetch('book__images', queryset=BookImage.objects.order_by('sort_order', 'id')),
        )
    )


def accessible_conversation(request, conversation_id):
    conversation = get_object_or_404(conversation_queryset(), pk=conversation_id)
    if request.user.id not in (conversation.buyer_id, conversation.seller_id):
        raise PermissionDenied('Bạn không có quyền truy cập cuộc hội thoại này.')
    return conversation


class ConversationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        if book.status in ('deleted', 'hidden'):
            raise serializers.ValidationError({'book': 'Sách không còn khả dụng để liên hệ.'})
        if book.seller_id == request.user.id:
            return Response(
                {'detail': 'Seller không thể tạo cuộc hội thoại với chính mình.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        with transaction.atomic():
            conversation, _ = Conversation.objects.get_or_create(
                book=book,
                buyer=request.user,
                seller_id=book.seller_id,
                defaults={'created_at': now, 'updated_at': now},
            )
        conversation = conversation_queryset().get(pk=conversation.pk)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = conversation_queryset().filter(
            Q(buyer_id=request.user.id) | Q(seller_id=request.user.id),
        ).order_by('-updated_at', '-id')
        return Response(ConversationSerializer(conversations, many=True).data)


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = accessible_conversation(request, conversation_id)
        return Response(ConversationSerializer(conversation).data)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = accessible_conversation(request, conversation_id)
        messages = conversation.messages.select_related('sender').order_by('created_at', 'id')
        return Response({
            'conversation_id': conversation.id,
            'results': MessageSerializer(messages, many=True).data,
        })

    def post(self, request, conversation_id):
        conversation = accessible_conversation(request, conversation_id)
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            message = serializer.save(
                conversation=conversation,
                sender=request.user,
                created_at=timezone.now(),
            )
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=['updated_at'])
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
