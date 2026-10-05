from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase, override_settings
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
        queryset.filter.return_value.count.return_value = 3
        paginator = Mock()
        paginator.paginate_queryset.return_value = []
        paginator.get_paginated_response.side_effect = lambda data: Response({'results': data})
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
        self.assertEqual(response.data['unread_count'], 3)
        filter_notifications.assert_called_once_with(user_id=self.user.id)
        queryset.order_by.assert_called_once_with('-created_at', '-id')
        queryset.filter.assert_called_once_with(is_read=False)

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


class OrderNotificationTests(SimpleTestCase):
    def test_borrow_notification_is_created_once_for_each_party(self):
        from notifications.services import notify_borrow_order_parties

        borrow = SimpleNamespace(id=31, borrower_id=7, lender_id=8)
        with patch('notifications.services.Notification.objects.create') as create:
            notify_borrow_order_parties(
                borrow,
                title='Sách đã giao',
                content='Phiếu đang hoạt động.',
            )

        self.assertEqual(
            [call.kwargs['user_id'] for call in create.call_args_list],
            [7, 8],
        )
        for call in create.call_args_list:
            self.assertEqual(call.kwargs['notification_type'], 'BORROW_ORDER')
            self.assertEqual(call.kwargs['entity_type'], 'BORROW_ORDER')
            self.assertEqual(call.kwargs['entity_id'], 31)
            self.assertFalse(call.kwargs['is_read'])
            self.assertIsNotNone(call.kwargs['created_at'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_order_notification_is_created_for_each_party_and_emails_after_commit(self):
        from notifications.services import notify_order_parties

        buyer = SimpleNamespace(id=1, email='buyer@example.test', full_name='Buyer')
        seller = SimpleNamespace(id=2, email='seller@example.test', full_name='Seller')
        order = SimpleNamespace(
            id=22,
            order_code='ORD-22',
            status='CONFIRMED',
            buyer=buyer,
            seller=seller,
        )
        notifications = []
        callbacks = []

        with patch(
            'notifications.services.Notification.objects.create',
            side_effect=lambda **kwargs: notifications.append(kwargs),
        ), patch(
            'notifications.services.transaction.on_commit',
            side_effect=lambda callback: callbacks.append(callback),
        ), patch('notifications.services.send_mail', return_value=1) as send_mail:
            notify_order_parties(
                order,
                title='Đặt hàng thành công',
                content='Đơn hàng đã được tạo.',
            )
            self.assertEqual([item['user_id'] for item in notifications], [1, 2])
            self.assertEqual([item['entity_id'] for item in notifications], [22, 22])
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            self.assertEqual(send_mail.call_count, 2)
            self.assertEqual(send_mail.call_args_list[0].args[3], ['buyer@example.test'])
            self.assertEqual(send_mail.call_args_list[1].args[3], ['seller@example.test'])

    def test_status_notification_is_not_created_when_status_is_unchanged(self):
        from notifications.services import notify_order_status_changed

        order = SimpleNamespace(status='CONFIRMED')
        with patch('notifications.services.Notification.objects.create') as create:
            notify_order_status_changed(order, 'CONFIRMED')
        create.assert_not_called()
