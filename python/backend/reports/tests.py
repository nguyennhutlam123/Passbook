from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from .admin_api_views import AdminReportDetailView, AdminReportUpdateSerializer
from .api_views import MyReportListView
from .dashboard_api_views import AdminDashboardView
from .models import Report


class ReportModerationSerializerTests(SimpleTestCase):
    def test_admin_report_status_values_are_validated(self):
        serializer = AdminReportUpdateSerializer(data={
            'status': 'IN_REVIEW',
            'resolution_note': 'Reviewing evidence',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        invalid = AdminReportUpdateSerializer(data={'status': 'DELETED'})
        self.assertFalse(invalid.is_valid())


class ReportAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(id=10, is_authenticated=True, role='STUDENT')

    def test_report_list_is_scoped_to_reporter(self):
        queryset = Mock()
        queryset.select_related.return_value = queryset
        queryset.order_by.return_value = queryset
        paginator = Mock()
        paginator.paginate_queryset.return_value = []
        paginator.get_paginated_response.side_effect = lambda data: Response(data)
        request = self.factory.get('/api/reports/mine/')
        force_authenticate(request, user=self.user)

        with patch.object(
            Report.objects,
            'filter',
            return_value=queryset,
        ) as filter_reports, patch(
            'reports.api_views.BookPagination',
            return_value=paginator,
        ):
            response = MyReportListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        filter_reports.assert_called_once_with(reporter_id=self.user.id)

    def test_nonadmin_cannot_process_reports(self):
        request = self.factory.patch(
            '/api/admin/reports/42/',
            {'status': 'RESOLVED'},
            format='json',
        )
        force_authenticate(request, user=self.user)

        with patch(
            'reports.admin_api_views.get_object_or_404',
        ) as get_report:
            response = AdminReportDetailView.as_view()(request, report_id=42)

        self.assertEqual(response.status_code, 403)
        get_report.assert_not_called()


class AdminDashboardApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_dashboard_is_admin_only(self):
        request = self.factory.get('/api/admin/dashboard/')
        force_authenticate(
            request,
            user=SimpleNamespace(
                id=3,
                is_authenticated=True,
                role='STUDENT',
            ),
        )

        with patch('reports.dashboard_api_views.get_dashboard_metrics') as metrics:
            response = AdminDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        metrics.assert_not_called()

    def test_admin_receives_aggregate_metrics_only(self):
        metrics_payload = {
            'users': {
                'total': 12,
                'active': 10,
                'locked': 2,
                'pending_verification': 0,
                'by_status': {'ACTIVE': 10, 'BLOCKED': 2},
            },
            'payments': {
                'total': 4,
                'paid': 0,
                'by_status': {'PENDING': 4},
            },
            'messages': 25,
        }
        request = self.factory.get('/api/admin/dashboard/')
        force_authenticate(
            request,
            user=SimpleNamespace(
                id=1,
                is_authenticated=True,
                role='ADMIN',
            ),
        )

        with patch(
            'reports.dashboard_api_views.get_dashboard_metrics',
            return_value=metrics_payload,
        ):
            response = AdminDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, metrics_payload)
        self.assertNotIn('password_hash', response.data)
