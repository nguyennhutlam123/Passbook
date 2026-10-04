from types import SimpleNamespace
from unittest.mock import patch

from books.pagination import BookPagination
from django.http import Http404
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from .api_views import ConversationDetailView, MessageListView
from .models import Conversation, ConversationMember
from .serializers import ConversationSerializer, MessageSerializer


class MessagePaginationTests(SimpleTestCase):
    def test_message_and_conversation_pages_are_bounded(self):
        self.assertEqual(BookPagination.page_size, 10)
        self.assertEqual(BookPagination.max_page_size, 50)
        self.assertEqual(BookPagination.page_size_query_param, 'page_size')

    def test_maximum_page_size_is_accepted(self):
        request = Request(APIRequestFactory().get('/messages/?page_size=50'))
        paginator = BookPagination()
        page = paginator.paginate_queryset(list(range(100)), request, view=None)
        self.assertEqual(len(page), 50)

    def test_oversized_page_size_is_rejected(self):
        request = Request(APIRequestFactory().get('/messages/?page_size=500'))
        with self.assertRaises(ValidationError):
            BookPagination().paginate_queryset(list(range(100)), request, view=None)


class ConversationAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = type('UserStub', (), {'id': 10, 'is_authenticated': True})()

    def test_nonmember_cannot_read_conversation_detail(self):
        request = self.factory.get('/api/conversations/42/')
        force_authenticate(request, user=self.user)

        with patch(
            'messaging.api_views.accessible_conversation',
            side_effect=PermissionDenied,
        ):
            response = ConversationDetailView.as_view()(
                request,
                conversation_id=42,
            )

        self.assertEqual(response.status_code, 403)

    def test_nonmember_message_list_is_not_found_and_does_not_mark_read(self):
        queryset = object()
        request = self.factory.get('/api/conversations/42/messages/')
        force_authenticate(request, user=self.user)

        with patch.object(
            Conversation.objects,
            'filter',
            return_value=queryset,
        ) as filter_conversations, patch(
            'messaging.api_views.get_object_or_404',
            side_effect=Http404,
        ), patch.object(ConversationMember.objects, 'filter') as filter_members:
            response = MessageListView.as_view()(
                request,
                conversation_id=42,
            )

        self.assertEqual(response.status_code, 404)
        filter_conversations.assert_called_once_with(
            members__user_id=self.user.id,
        )
        filter_members.assert_not_called()

    def test_nonmember_cannot_send_a_message(self):
        request = self.factory.post(
            '/api/conversations/42/messages/',
            {'content': 'forged message'},
            format='json',
        )
        force_authenticate(request, user=self.user)

        with patch(
            'messaging.api_views.accessible_conversation',
            side_effect=PermissionDenied,
        ), patch('messaging.api_views.MessageSerializer') as serializer:
            response = MessageListView.as_view()(
                request,
                conversation_id=42,
            )

        self.assertEqual(response.status_code, 403)
        serializer.assert_not_called()

    def test_anonymous_user_cannot_read_or_send_conversation_messages(self):
        get_response = MessageListView.as_view()(
            self.factory.get('/api/conversations/42/messages/'),
            conversation_id=42,
        )
        post_response = MessageListView.as_view()(
            self.factory.post(
                '/api/conversations/42/messages/',
                {'content': 'hello'},
                format='json',
            ),
            conversation_id=42,
        )

        self.assertEqual(get_response.status_code, 401)
        self.assertEqual(post_response.status_code, 401)

    def test_client_cannot_choose_message_sender_or_read_state(self):
        serializer = MessageSerializer(data={
            'content': ' hello ',
            'sender_id': 999,
            'is_read': True,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {'content': 'hello'})


class ConversationSerializationTests(SimpleTestCase):
    def test_conversation_with_missing_book_context_serializes_as_null(self):
        now = timezone.now()
        conversation = Conversation(
            id=4,
            conversation_type='SALE',
            created_at=now,
            updated_at=now,
        )
        conversation._prefetched_objects_cache = {
            'members': [
                SimpleNamespace(
                    user=SimpleNamespace(id=1, full_name='Buyer'),
                ),
                SimpleNamespace(
                    user=SimpleNamespace(id=2, full_name='Seller'),
                ),
            ],
        }

        payload = ConversationSerializer(conversation).data

        self.assertIsNone(payload['book'])
        self.assertEqual(payload['buyer']['name'], 'Buyer')
        self.assertEqual(payload['seller']['name'], 'Seller')
