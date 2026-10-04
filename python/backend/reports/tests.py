from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from .admin import ReportAdmin
from .admin_api_views import (
    AdminReportDetailView,
    AdminReportListView,
    AdminReportUpdateSerializer,
)
from . import dashboard
from .api_views import MyReportListView, ReportCreateView
from .dashboard_api_views import AdminDashboardSectionView, AdminDashboardView
from .models import Report
from .serializers import ReportCreateSerializer


class ReportCreateValidationTests(SimpleTestCase):
    def test_report_requires_exactly_one_target(self):
        serializer = ReportCreateSerializer(data={
            'reason': 'SPAM',
            'description': 'Suspicious listing',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_report_rejects_unknown_reason(self):
        serializer = ReportCreateSerializer(data={
            'reason': 'SOME_UNSUPPORTED_REASON',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('reason', serializer.errors)

    def test_report_reason_choices_cover_supported_cases(self):
        self.assertEqual(
            set(ReportCreateSerializer().fields['reason'].choices),
            {
                'INAPPROPRIATE_CONTENT',
                'INCORRECT_BOOK_INFO',
                'SPAM',
                'SCAM',
                'POLICY_VIOLATION',
                'OTHER',
            },
        )


class ReportModerationSerializerTests(SimpleTestCase):
    def test_admin_report_status_values_are_validated(self):
        serializer = AdminReportUpdateSerializer(data={
            'status': 'IN_REVIEW',
            'resolution_note': 'Reviewing evidence',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        invalid = AdminReportUpdateSerializer(data={'status': 'DELETED'})
        self.assertFalse(invalid.is_valid())

    def test_terminal_status_requires_resolution_note(self):
        serializer = AdminReportUpdateSerializer(data={'status': 'RESOLVED'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('resolution_note', serializer.errors)


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

    def test_admin_report_list_filters_by_a_valid_status(self):
        self.user.role = 'ADMIN'
        queryset = Mock()
        queryset.select_related.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.filter.return_value = queryset
        paginator = Mock()
        paginator.paginate_queryset.return_value = []
        paginator.get_paginated_response.side_effect = lambda data: Response(data)
        request = self.factory.get('/api/admin/reports/', {'status': 'OPEN'})
        force_authenticate(request, user=self.user)

        with patch.object(
            Report.objects,
            'select_related',
            return_value=queryset,
        ), patch(
            'reports.admin_api_views.BookPagination',
            return_value=paginator,
        ):
            response = AdminReportListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called_once_with(status='OPEN')

    def test_admin_report_list_rejects_unknown_status(self):
        self.user.role = 'ADMIN'
        request = self.factory.get('/api/admin/reports/', {'status': 'INVALID'})
        force_authenticate(request, user=self.user)

        with patch.object(Report.objects, 'select_related') as select_related:
            response = AdminReportListView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        select_related.assert_called_once()


class ReportCreationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.reporter = SimpleNamespace(
            id=18,
            pk=18,
            is_authenticated=True,
            role='STUDENT',
        )
        self.target_user = SimpleNamespace(id=29, status='ACTIVE')
        self.report = SimpleNamespace(
            id=52,
            status='OPEN',
            reason='SPAM',
            description='Suspicious seller',
            created_at=None,
            resolved_at=None,
            book=None,
        )

    def test_create_sets_pending_database_state_and_deduplicates(self):
        request = self.factory.post(
            '/api/reports/',
            {'reported_user_id': 29, 'reason': 'SPAM', 'description': 'Suspicious seller'},
            format='json',
        )
        force_authenticate(request, user=self.reporter)
        query = Mock()
        query.first.return_value = None

        with patch(
            'reports.api_views.ReportCreateSerializer',
        ) as serializer_class, patch.object(
            Report.objects,
            'filter',
            return_value=query,
        ) as find_duplicate, patch.object(
            Report.objects,
            'create',
            return_value=self.report,
        ) as create_report, patch(
            'reports.api_views.User.objects.select_for_update',
        ) as lock_user, patch(
            'reports.api_views.ReportSerializer',
        ) as response_serializer, patch(
            'reports.api_views.transaction.atomic',
            return_value=nullcontext(),
        ):
            serializer = serializer_class.return_value
            serializer.validated_data = {
                'reported_user': self.target_user,
                'reason': 'SPAM',
                'description': 'Suspicious seller',
            }
            response_serializer.return_value.data = {'id': 52, 'status': 'pending'}
            response = ReportCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'pending')
        find_duplicate.assert_called_once_with(
            reporter=self.reporter,
            reason='SPAM',
            status__in=('OPEN', 'IN_REVIEW'),
            reported_user=self.target_user,
        )
        create_report.assert_called_once()
        self.assertEqual(create_report.call_args.kwargs['status'], 'OPEN')
        lock_user.return_value.get.assert_called_once_with(pk=self.reporter.id)

        query.first.return_value = self.report
        create_report.reset_mock()
        request = self.factory.post(
            '/api/reports/',
            {'reported_user_id': 29, 'reason': 'SPAM'},
            format='json',
        )
        force_authenticate(request, user=self.reporter)
        with patch('reports.api_views.ReportCreateSerializer') as serializer_class, patch.object(
            Report.objects,
            'filter',
            return_value=query,
        ), patch(
            'reports.api_views.User.objects.select_for_update',
        ), patch(
            'reports.api_views.ReportSerializer',
        ) as response_serializer, patch(
            'reports.api_views.transaction.atomic',
            return_value=nullcontext(),
        ):
            serializer_class.return_value.validated_data = {
                'reported_user': self.target_user,
                'reason': 'SPAM',
            }
            response_serializer.return_value.data = {'id': 52, 'status': 'pending'}
            response = ReportCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        create_report.assert_not_called()

    def test_unauthenticated_user_cannot_create_report(self):
        request = self.factory.post(
            '/api/reports/',
            {'reported_user_id': 29, 'reason': 'SPAM'},
            format='json',
        )
        with patch.object(
            Report.objects,
            'create',
        ) as create_report, patch(
            'reports.api_views.ReportCreateSerializer',
        ):
            response = ReportCreateView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        create_report.assert_not_called()


class ReportAdminTests(SimpleTestCase):
    def test_admin_save_maps_handler_to_passbook_admin_or_none(self):
        model_admin = ReportAdmin(Report, admin.site)
        obj = Mock()
        obj.status = 'RESOLVED'
        request = SimpleNamespace(user=SimpleNamespace(pk=8))
        passbook_admin = SimpleNamespace(id=8, role='ADMIN')
        obj.save = Mock()

        with patch(
            'reports.admin.PassbookUser.objects.filter',
        ) as find_handler:
            find_handler.return_value.first.return_value = passbook_admin
            model_admin.save_model(request, obj, form=Mock(), change=True)

        find_handler.assert_called_once_with(pk=8, role='ADMIN')
        self.assertIs(obj.handled_by, passbook_admin)
        self.assertIsNotNone(obj.resolved_at)
        obj.save.assert_called_once_with()


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

    def test_dashboard_sections_are_admin_only(self):
        for user in (
            None,
            SimpleNamespace(id=3, is_authenticated=True, role='STUDENT'),
        ):
            request = self.factory.get('/api/admin/dashboard/users/')
            if user is not None:
                force_authenticate(request, user=user)
            section = Mock(return_value={})
            with patch.dict(
                'reports.dashboard_api_views.DASHBOARD_SECTIONS',
                {'users': section},
            ):
                response = AdminDashboardSectionView.as_view()(
                    request,
                    section='users',
                )
            self.assertIn(response.status_code, (401, 403))
            section.assert_not_called()

    def test_admin_can_read_dashboard_section(self):
        request = self.factory.get('/api/admin/dashboard/users/')
        force_authenticate(
            request,
            user=SimpleNamespace(
                id=1,
                is_authenticated=True,
                role='ADMIN',
            ),
        )
        payload = {'total': 2, 'active': 2}
        with patch.dict(
            'reports.dashboard_api_views.DASHBOARD_SECTIONS',
            {'users': lambda: payload},
        ):
            response = AdminDashboardSectionView.as_view()(
                request,
                section='users',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)

    def test_invalid_analytics_period_is_rejected(self):
        request = self.factory.get(
            '/api/admin/dashboard/analytics/?period=invalid',
        )
        force_authenticate(
            request,
            user=SimpleNamespace(
                id=1,
                is_authenticated=True,
                role='ADMIN',
            ),
        )
        with patch('reports.dashboard_api_views.analytics_dashboard', return_value={
            'error': 'period must be one of: day, week, month, year',
        }):
            response = AdminDashboardSectionView.as_view()(
                request,
                section='analytics',
            )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_sections_return_empty_metrics_without_data(self):
        class EmptyQuerySet:
            def all(self):
                return self

            def filter(self, **_kwargs):
                return self

            def exclude(self, **_kwargs):
                return self

            def values(self, *_args, **_kwargs):
                return self

            def annotate(self, **_kwargs):
                return self

            def order_by(self, *_args):
                return self

            def distinct(self):
                return self

            def aggregate(self, **kwargs):
                return {
                    key: None if key in ('avg', 'average') else 0
                    for key in kwargs
                }

            def count(self):
                return 0

            def __iter__(self):
                return iter(())

            def __getitem__(self, _key):
                return self

        models = (
            dashboard.BookRequest,
            dashboard.BookReservation,
            dashboard.BookWork,
            dashboard.BorrowOrder,
            dashboard.Cart,
            dashboard.Category,
            dashboard.Favorite,
            dashboard.LendListing,
            dashboard.Order,
            dashboard.Payment,
            dashboard.Refund,
            dashboard.Return,
            dashboard.Review,
            dashboard.SaleListing,
            dashboard.Shipment,
            dashboard.Conversation,
            dashboard.Message,
            dashboard.Notification,
            dashboard.Report,
            dashboard.Subject,
            dashboard.University,
            dashboard.User,
        )
        with ExitStack() as stack:
            for model in models:
                stack.enter_context(patch.object(model, 'objects', EmptyQuerySet()))
            for section, handler in dashboard.DASHBOARD_SECTIONS.items():
                result = handler()
                self.assertIsInstance(result, dict, section)
            result = dashboard.analytics_dashboard({'period': 'day'})
            self.assertEqual(result['users'], [])
            self.assertEqual(result['listings'], [])
