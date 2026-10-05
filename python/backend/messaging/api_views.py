from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from books.api_views import optimized_books_queryset
from books.pagination import BookPagination
from books.models import Book
from .models import Conversation, ConversationMember, Message
from .serializers import ConversationSerializer, MessageSerializer
from users.models import User


def conversation_queryset():
    return Conversation.objects.prefetch_related(
        Prefetch(
            'members',
            queryset=ConversationMember.objects.select_related('user')
            .order_by('joined_at', 'user_id'),
        ),
        Prefetch(
            'messages',
            queryset=Message.objects.filter(
                deleted_at__isnull=True,
            ).order_by('-sent_at', '-id')[:1],
            to_attr='latest_messages',
        ),
    )


def accessible_conversation(request, conversation_id):
    conversation = get_object_or_404(
        conversation_queryset(),
        pk=conversation_id,
    )
    if not ConversationMember.objects.filter(
        conversation_id=conversation.id,
        user_id=request.user.id,
    ).exists():
        raise PermissionDenied('Bạn không có quyền truy cập cuộc hội thoại này.')
    return conversation


class ConversationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(
            optimized_books_queryset(primary_images_only=True),
            pk=book_id,
            status='AVAILABLE',
        )
        if book.owner_id == request.user.id:
            return Response(
                {'detail': 'Seller không thể tạo cuộc hội thoại với chính mình.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        participant_ids = sorted({request.user.id, book.owner_id})
        with transaction.atomic():
            list(
                User.objects.select_for_update()
                .filter(pk__in=participant_ids)
                .order_by('pk')
                .values_list('pk', flat=True)
            )
            candidate_ids = ConversationMember.objects.filter(
                user_id=request.user.id,
            ).values('conversation_id')
            participant_count = (
                ConversationMember.objects
                .filter(conversation_id=OuterRef('pk'))
                .values('conversation_id')
                .annotate(total=Count('user_id'))
                .values('total')
            )
            existing = (
                Conversation.objects
                .filter(conversation_type='SALE', id__in=candidate_ids)
                .annotate(member_count=Subquery(participant_count))
                .filter(members__user_id=book.owner_id, member_count=2)
                .order_by('-updated_at', '-id')
                .first()
            )
            created = existing is None
            if existing is None:
                conversation = Conversation.objects.create(
                    conversation_type='SALE',
                    created_at=now,
                    updated_at=now,
                )
                ConversationMember.objects.bulk_create([
                    ConversationMember(
                        conversation=conversation,
                        user_id=request.user.id,
                        joined_at=now,
                    ),
                    ConversationMember(
                        conversation=conversation,
                        user_id=book.owner_id,
                        joined_at=now + timedelta(milliseconds=1),
                    ),
                ])
            else:
                conversation = existing
        conversation = conversation_queryset().get(pk=conversation.pk)
        conversation.book_context = book
        return Response(
            ConversationSerializer(
                conversation,
                context={'request': request},
            ).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = ConversationMember.objects.filter(
            conversation_id=OuterRef('pk'),
            user_id=request.user.id,
        )
        conversations = (
            conversation_queryset()
            .filter(Exists(member))
            .order_by('-updated_at', '-id')
        )
        paginator = BookPagination()
        page = paginator.paginate_queryset(conversations, request, view=self)
        return paginator.get_paginated_response(
            ConversationSerializer(
                page,
                many=True,
                context={'request': request},
            ).data,
        )


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = accessible_conversation(request, conversation_id)
        return Response(ConversationSerializer(
            conversation,
            context={'request': request},
        ).data)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation.objects.filter(members__user_id=request.user.id),
            pk=conversation_id,
        )
        now = timezone.now()
        ConversationMember.objects.filter(
            conversation=conversation,
            user=request.user,
        ).update(last_read_at=now)
        recipient_last_read_at = ConversationMember.objects.filter(
            conversation_id=conversation.id,
        ).exclude(
            user_id=OuterRef('sender_id'),
        ).values('last_read_at')[:1]
        messages = conversation.messages.filter(
            deleted_at__isnull=True,
        ).select_related('sender').annotate(
            reader_last_read_at=Subquery(recipient_last_read_at),
        ).order_by('sent_at', 'id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(messages, request, view=self)
        response = paginator.get_paginated_response(
            MessageSerializer(page, many=True).data,
        )
        response.data['conversation_id'] = conversation.id
        return response

    def post(self, request, conversation_id):
        conversation = accessible_conversation(request, conversation_id)
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        with transaction.atomic():
            message = serializer.save(
                conversation=conversation,
                sender=request.user,
                message_type='TEXT',
                sent_at=now,
            )
            conversation.updated_at = now
            conversation.save(update_fields=['updated_at'])
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )
