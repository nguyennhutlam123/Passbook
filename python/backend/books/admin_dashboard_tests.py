from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from .admin_dashboard_views import (
    AdminBorrowOrderDetailView,
    AdminBorrowOrderListView,
    AdminReservationDetailView,
    AdminReservationListView,
    _apply_admin_filters,
)
class AdminReservationBorrowDashboardTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = SimpleNamespace(id=1, is_authenticated=True, role='ADMIN')

    def test_admin_list_and_detail_views_require_admin(self):
        views = (
            (AdminReservationListView.as_view(), {}),
            (AdminReservationDetailView.as_view(), {'reservation_id': 1}),
            (AdminBorrowOrderListView.as_view(), {}),
            (AdminBorrowOrderDetailView.as_view(), {'borrow_order_id': 1}),
        )
        for view, kwargs in views:
            anonymous = self.factory.get('/api/admin/dashboard/reservations/')
            self.assertEqual(view(anonymous, **kwargs).status_code, 401)

            request = self.factory.get('/api/admin/dashboard/reservations/')
            force_authenticate(
                request,
                user=Mock(id=2, is_authenticated=True, role='STUDENT'),
            )
            self.assertEqual(view(request, **kwargs).status_code, 403)

    def test_reservation_and_borrow_filters_include_pending_and_supported_fields(self):
        for is_borrow in (False, True):
            queryset = Mock()
            queryset.filter.return_value = queryset
            queryset.distinct.return_value = queryset
            request = Request(self.factory.get(
                '/api/admin/dashboard/?status=PENDING&user=9&book=12&listing=14'
                '&start_date=2026-10-01&end_date=2026-10-04',
            ))
            filtered = _apply_admin_filters(queryset, request, borrow=is_borrow)
            self.assertIs(filtered, queryset)
            calls = [call.kwargs for call in queryset.filter.call_args_list]
            self.assertTrue(any(call.get('status') == 'PENDING' for call in calls))
            self.assertTrue(any('created_at__date__gte' in call for call in calls))
            self.assertTrue(any('created_at__date__lte' in call for call in calls))
            self.assertGreaterEqual(len(calls), 5)
            if is_borrow:
                self.assertTrue(any(call.get('lend_listing_id') == 14 for call in calls))
            else:
                    self.assertTrue(any(
                        'book__sale_listings__id' in str(call.args)
                        for call in queryset.filter.call_args_list
                    ))

    def test_invalid_filter_dates_are_rejected(self):
        queryset = Mock()
        request = Request(self.factory.get('/?start_date=not-a-date'))
        with self.assertRaises(ValidationError):
            _apply_admin_filters(queryset, request)

    def test_invalid_reservation_and_borrow_status_filters_are_rejected(self):
        for is_borrow in (False, True):
            queryset = Mock()
            request = Request(self.factory.get('/?status=NOT_A_STATUS'))
            with self.assertRaises(ValidationError):
                _apply_admin_filters(queryset, request, borrow=is_borrow)

    def test_admin_can_page_reservations_and_borrow_orders(self):
        item = object()
        for view_class, payload_method in (
            (AdminReservationListView, 'payload'),
            (AdminBorrowOrderListView, 'payload'),
        ):
            request = self.factory.get('/?status=PENDING&page=1&page_size=2')
            force_authenticate(request, user=self.admin)
            with patch.object(view_class, 'get_queryset', return_value=[item]), patch(
                'books.admin_dashboard_views.BookPagination',
            ) as paginator_class, patch.object(
                view_class,
                payload_method,
                return_value={'id': 3, 'status': 'PENDING'},
            ):
                paginator = paginator_class.return_value
                paginator.paginate_queryset.return_value = [item]
                paginator.get_paginated_response.side_effect = (
                    lambda data: Response({'results': data})
                )
                response = view_class.as_view()(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['results'][0]['status'], 'PENDING')
            paginator.paginate_queryset.assert_called_once()
            paginator.get_paginated_response.assert_called_once()

    def test_admin_can_view_reservation_and_borrow_details(self):
        item = object()
        for view_class, method_name, key in (
            (AdminReservationDetailView, 'get_queryset', 'reservation_id'),
            (AdminBorrowOrderDetailView, 'get_queryset', 'borrow_order_id'),
        ):
            request = self.factory.get('/api/admin/dashboard/detail/')
            force_authenticate(request, user=self.admin)
            with patch.object(view_class, method_name, return_value=[item]), patch(
                'books.admin_dashboard_views.get_object_or_404',
                return_value=item,
            ), patch.object(
                view_class,
                'payload',
                return_value={'id': 7, 'status': 'PENDING'},
            ):
                response = view_class.as_view()(request, **{key: 7})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {'id': 7, 'status': 'PENDING'})
