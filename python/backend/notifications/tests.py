from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from .api_views import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
)
from .models import Notification


class NotificationAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(id=10, is_authenticated=True)

    def test_list_queryset_is_scoped_to_authenticated_user(self):
        queryset = Mock()
        queryset.order_by.return_value = queryset
        paginator = Mock()
        paginator.paginate_queryset.return_value = []
        paginator.get_paginated_response.side_effect = lambda data: Response(data)
        request = self.factory.get('/api/notifications/')
        force_authenticate(request, user=self.user)

        with patch.object(
            Notification.objects,
            'filter',
            return_value=queryset,
        ) as filter_notifications, patch(
            'notifications.api_views.BookPagination',
            return_value=paginator,
        ):
            response = NotificationListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        filter_notifications.assert_called_once_with(user_id=self.user.id)
        queryset.order_by.assert_called_once_with('-created_at', '-id')

    def test_user_cannot_mark_another_users_notification_read(self):
        request = self.factory.patch('/api/notifications/41/read/')
        force_authenticate(request, user=self.user)

        with patch(
            'notifications.api_views.get_object_or_404',
            side_effect=Http404,
        ) as get_notification:
            response = NotificationReadView.as_view()(request, notification_id=41)

        self.assertEqual(response.status_code, 404)
        get_notification.assert_called_once_with(
            Notification,
            pk=41,
            user=self.user,
        )

    def test_mark_all_read_updates_only_authenticated_users_notifications(self):
        queryset = Mock()
        queryset.update.return_value = 2
        request = self.factory.patch('/api/notifications/read-all/')
        force_authenticate(request, user=self.user)

        with patch.object(
            Notification.objects,
            'filter',
            return_value=queryset,
        ) as filter_notifications:
            response = NotificationReadAllView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'updated_count': 2})
        filter_notifications.assert_called_once_with(
            user_id=self.user.id,
            is_read=False,
        )
        queryset.update.assert_called_once_with(is_read=True)

    def test_anonymous_user_cannot_list_or_update_notifications(self):
        list_response = NotificationListView.as_view()(
            self.factory.get('/api/notifications/'),
        )
        update_response = NotificationReadView.as_view()(
            self.factory.patch('/api/notifications/41/read/'),
            notification_id=41,
        )

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(update_response.status_code, 401)
