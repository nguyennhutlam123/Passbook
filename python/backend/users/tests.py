import logging
import re
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import check_password, make_password
from django.http import Http404
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from .admin_api_views import (
    AdminUserListView,
    UserAccountStatusSerializer,
    UserViolationInputSerializer,
    UserViolationStatusSerializer,
)
from .api_views import (
    ActiveUserTokenRefreshSerializer,
    LogoutView,
    UserAddressDetailView,
    UserAddressListCreateView,
)
from .models import OtpVerification, User, UserAddress
from .otp_api_views import OtpVerifySerializer, OtpVerifyView
from .permissions import IsAdmin
from .tokens import is_token_revoked, revoke_token


class AdminUserListApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_admin_user_list_is_paginated_and_excludes_password_hash(self):
        admin = SimpleNamespace(id=1, is_authenticated=True, role='ADMIN')
        user = User(
            id=17,
            email='student@example.invalid',
            password_hash='never-return-this',
            full_name='Synthetic Student',
            phone=None,
            role='STUDENT',
            status='ACTIVE',
            university=None,
            created_at=timezone.now(),
        )
        queryset = Mock()
        queryset.select_related.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.filter.return_value = queryset
        paginator = Mock()
        paginator.paginate_queryset.return_value = [user]
        paginator.get_paginated_response.side_effect = lambda data: Response(data)
        request = self.factory.get(
            '/api/admin/users/',
            {'search': 'student', 'status': 'ACTIVE', 'role': 'STUDENT'},
        )
        force_authenticate(request, user=admin)

        with patch.object(
            User.objects,
            'select_related',
            return_value=queryset,
        ), patch(
            'users.admin_api_views.BookPagination',
            return_value=paginator,
        ):
            response = AdminUserListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], 17)
        self.assertEqual(response.data[0]['email'], 'student@example.invalid')
        self.assertNotIn('password_hash', response.data[0])
        queryset.filter.assert_any_call(status='ACTIVE')
        queryset.filter.assert_any_call(role='STUDENT')
        paginator.paginate_queryset.assert_called_once()

    def test_nonadmin_cannot_list_users(self):
        request = self.factory.get('/api/admin/users/')
        force_authenticate(
            request,
            user=SimpleNamespace(id=2, is_authenticated=True, role='STUDENT'),
        )

        with patch.object(User.objects, 'select_related') as select_related:
            response = AdminUserListView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        select_related.assert_not_called()


class _OtpQuery:
    def __init__(self, manager, filters=None):
        self.manager = manager
        self.filters = filters or {}

    def select_for_update(self):
        return self

    def filter(self, **filters):
        return _OtpQuery(self.manager, {**self.filters, **filters})

    def order_by(self, *_fields):
        return self

    def first(self):
        matches = [
            row for row in self.manager.rows
            if all(getattr(row, key) == value for key, value in self.filters.items())
        ]
        return matches[-1] if matches else None

    def exists(self):
        return self.first() is not None


class _OtpManager:
    def __init__(self):
        self.rows = []

    def select_for_update(self):
        return _OtpQuery(self)

    def filter(self, **filters):
        return _OtpQuery(self, filters)

    def create(self, **values):
        values.setdefault(
            'user_id',
            getattr(values.get('user'), 'id', None),
        )
        row = SimpleNamespace(id=len(self.rows) + 1, **values)
        row.save = lambda update_fields=None: None
        self.rows.append(row)
        return row


class DjangoSMTPEmailServiceTests(SimpleTestCase):
    @override_settings(DEFAULT_FROM_EMAIL='passbook@example.test')
    def test_send_email_uses_django_mail_with_configured_sender(self):
        from users.services.email import send_email

        with patch(
            'users.services.email.django_send_mail',
            return_value=1,
        ) as django_send_mail:
            send_email(
                recipient='student@example.test',
                subject='Passbook verification code',
                text='Your verification code is 654321.',
            )

        django_send_mail.assert_called_once_with(
            'Passbook verification code',
            'Your verification code is 654321.',
            'passbook@example.test',
            ['student@example.test'],
            fail_silently=False,
        )

    def test_smtp_failure_is_sanitized_and_logged_without_exception_message(self):
        import smtplib

        from users.services.email import EmailProviderError, send_email

        exception_detail = 'authentication failed'
        with patch(
            'users.services.email.django_send_mail',
            side_effect=smtplib.SMTPAuthenticationError(
                535,
                exception_detail.encode(),
            ),
        ), self.assertLogs('users.services.email', level='WARNING') as logs:
            with self.assertRaises(EmailProviderError) as raised:
                send_email(
                    recipient='student@example.test',
                    subject='Verification',
                    text='Your code is 654321.',
                )

        self.assertNotIn(exception_detail, str(raised.exception))
        self.assertNotIn(exception_detail, '\n'.join(logs.output))
        self.assertIn('OTP email sending failed (SMTPAuthenticationError).', logs.output[0])

    def test_email_backend_rejecting_message_is_a_delivery_error(self):
        from users.services.email import EmailProviderError, send_email

        with patch('users.services.email.django_send_mail', return_value=0):
            with self.assertRaises(EmailProviderError):
                send_email(
                    recipient='student@example.test',
                    subject='Verification',
                    text='Your code is 654321.',
                )


class OtpServiceTests(SimpleTestCase):
    def setUp(self):
        self.manager = _OtpManager()
        self.manager_patch = patch.object(OtpVerification, 'objects', self.manager)
        self.manager_patch.start()
        self.addCleanup(self.manager_patch.stop)
        self.atomic_patch = patch(
            'users.services.otp.transaction.atomic',
            return_value=nullcontext(),
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    @override_settings(
        OTP_LIFETIME_SECONDS=300,
        OTP_MAX_ATTEMPTS=5,
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=5,
    )
    def test_phone_otp_send_verify_and_reuse_protection(self):
        from .services.otp import (
            OtpVerificationError,
            issue_otp,
            verify_otp,
        )

        user = SimpleNamespace(id=71, pk=71, phone='+15550007777')
        delivered_codes = []
        with patch(
            'users.services.otp.User.objects.select_for_update',
        ) as lock_user, patch(
            'users.services.otp._deliver_otp',
            side_effect=lambda *, target, channel, purpose, code: delivered_codes.append(code),
        ):
            lock_user.return_value.get.return_value = user
            verification = issue_otp(
                target=user.phone,
                channel='PHONE',
                purpose='CHANGE_PHONE',
                user=user,
            )

        self.assertEqual(len(delivered_codes), 1)
        self.assertEqual(verification.status, 'PENDING')
        self.assertNotEqual(verification.otp_hash, delivered_codes[0])
        verified = verify_otp(
            target=user.phone,
            purpose='CHANGE_PHONE',
            code=delivered_codes[0],
            user_id=user.id,
        )
        self.assertEqual(verified.status, 'VERIFIED')
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=user.phone,
                purpose='CHANGE_PHONE',
                code=delivered_codes[0],
                user_id=user.id,
            )
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=user.phone,
                purpose='CHANGE_PHONE',
                code=delivered_codes[0],
                user_id=user.id + 1,
            )
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target='+15550009999',
                purpose='CHANGE_PHONE',
                code=delivered_codes[0],
                user_id=user.id,
            )

    @override_settings(
        OTP_LIFETIME_SECONDS=300,
        OTP_MAX_ATTEMPTS=5,
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=5,
        DEFAULT_FROM_EMAIL='test@passbook.invalid',
    )
    def test_email_otp_is_hashed_and_not_in_api_serializer_output(self):
        from .services.otp import issue_otp

        with patch('users.services.otp.secrets.randbelow', return_value=271):
            with patch('users.services.otp.send_email') as send_email:
                row = issue_otp(
                    target='Student@Example.com',
                    channel='EMAIL',
                    purpose='REGISTER',
                )
        self.assertEqual(row.target, 'student@example.com')
        self.assertEqual(row.status, 'PENDING')
        self.assertTrue(check_password('000271', row.otp_hash))
        self.assertNotEqual(row.otp_hash, '000271')
        send_email.assert_called_once()
        self.assertEqual(
            send_email.call_args.kwargs['recipient'],
            'student@example.com',
        )
        self.assertIn('000271', send_email.call_args.kwargs['text'])
        serializer = OtpVerifySerializer(data={
            'target': 'student@example.com',
            'purpose': 'REGISTER',
            'otp': '000271',
        })
        self.assertTrue(serializer.is_valid())
        self.assertNotIn('otp', serializer.data)

    def test_email_otp_is_randomly_generated_and_delivered(self):
        from .services.otp import issue_otp

        with patch(
            'users.services.otp.secrets.randbelow',
            return_value=456,
        ), patch('users.services.otp.send_email') as send_email:
            row = issue_otp(
                target='student@example.com',
                channel='EMAIL',
                purpose='REGISTER',
            )
        self.assertTrue(check_password('000456', row.otp_hash))
        self.assertNotEqual(row.otp_hash, '000456')
        send_email.assert_called_once()
        self.assertIn('000456', send_email.call_args.kwargs['text'])

    @override_settings(OTP_MAX_ATTEMPTS=2)
    def test_random_email_otp_expires_and_attempt_limit_blocks_verification(self):
        from .services.otp import OtpVerificationError, issue_otp, verify_otp

        with patch('users.services.otp.secrets.randbelow', return_value=314159), patch(
            'users.services.otp.send_email',
        ):
            expired = issue_otp(
                target='expired@example.com',
                channel='EMAIL',
                purpose='REGISTER',
            )
            expired.expires_at = timezone.now() - timedelta(seconds=1)
            with self.assertRaises(OtpVerificationError):
                verify_otp(
                    target=expired.target,
                    purpose='REGISTER',
                    code='314159',
                )
            self.assertEqual(expired.status, 'EXPIRED')

            blocked = issue_otp(
                target='attempt-limit@example.com',
                channel='EMAIL',
                purpose='REGISTER',
            )
            for _ in range(2):
                with self.assertRaises(OtpVerificationError):
                    verify_otp(
                        target=blocked.target,
                        purpose='REGISTER',
                        code='000000',
                    )
            self.assertEqual(blocked.status, 'BLOCKED')
            with self.assertRaises(OtpVerificationError):
                verify_otp(
                    target=blocked.target,
                    purpose='REGISTER',
                    code='314159',
                )

    @override_settings(
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=1,
        OTP_LIFETIME_SECONDS=300,
    )
    def test_random_email_otp_resend_keeps_cooldown_and_window_limits(self):
        from .services.otp import OtpRateLimitError, issue_otp

        with patch(
            'users.services.otp.secrets.randbelow',
            side_effect=(135790, 246801),
        ), patch('users.services.otp.send_email') as send_email:
            first = issue_otp(
                target='resend@example.com',
                channel='EMAIL',
                purpose='REGISTER',
            )
            with self.assertRaises(OtpRateLimitError):
                issue_otp(
                    target='resend@example.com',
                    channel='EMAIL',
                    purpose='REGISTER',
                )
            first.updated_at -= timedelta(seconds=61)
            second = issue_otp(
                target='resend@example.com',
                channel='EMAIL',
                purpose='REGISTER',
            )
        self.assertEqual(first.status, 'EXPIRED')
        self.assertEqual(second.resend_count, 1)
        self.assertTrue(check_password('246801', second.otp_hash))
        self.assertFalse(check_password('135790', second.otp_hash))
        self.assertEqual(send_email.call_count, 2)

    def test_smtp_failure_becomes_generic_otp_delivery_error(self):
        import smtplib

        from .services.otp import OtpDeliveryError, issue_otp

        with patch(
            'users.services.otp.secrets.randbelow',
            return_value=456789,
        ), patch(
            'users.services.email.django_send_mail',
            side_effect=smtplib.SMTPAuthenticationError(
                535,
                b'synthetic-app-password',
            ),
        ):
            with self.assertRaises(OtpDeliveryError) as raised:
                issue_otp(
                    target='student@example.com',
                    channel='EMAIL',
                    purpose='REGISTER',
                )
        self.assertNotIn('synthetic-app-password', str(raised.exception))

    @override_settings(
        OTP_LIFETIME_SECONDS=300,
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=5,
        PASSBOOK_SMS_DELIVERY_BACKEND='passbook.tests.send_sms',
    )
    def test_phone_otp_is_delivered_by_configured_adapter(self):
        from .services.otp import issue_otp

        sender = patch('users.services.otp.import_string', return_value=lambda *args: True)
        with sender, patch('users.services.otp.secrets.randbelow', return_value=72):
            row = issue_otp(
                target='+15550001111',
                channel='PHONE',
                purpose='CHANGE_PHONE',
            )
        self.assertTrue(check_password('000072', row.otp_hash))
        self.assertEqual(row.channel, 'PHONE')

    @override_settings(OTP_MAX_ATTEMPTS=5)
    def test_correct_otp_is_one_time_and_wrong_otp_increments_attempts(self):
        from .services.otp import OtpVerificationError, verify_otp

        now = timezone.now()
        row = self.manager.create(
            target='student@example.com',
            purpose='REGISTER',
            status='PENDING',
            otp_hash=make_password('654321'),
            expires_at=now + timedelta(minutes=5),
            attempt_count=0,
            updated_at=now,
            verified_at=None,
            user_id=1,
        )
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=row.target,
                purpose='REGISTER',
                code='000000',
            )
        self.assertEqual(row.attempt_count, 1)
        verified = verify_otp(
            target=row.target,
            purpose='REGISTER',
            code='654321',
        )
        self.assertEqual(verified.status, 'VERIFIED')
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=row.target,
                purpose='REGISTER',
                code='654321',
            )

    @override_settings(OTP_MAX_ATTEMPTS=2)
    def test_expired_and_attempt_limit_codes_are_invalidated(self):
        from .services.otp import OtpVerificationError, verify_otp

        now = timezone.now()
        expired = self.manager.create(
            target='expired@example.com',
            purpose='LOGIN',
            status='PENDING',
            otp_hash=make_password('654321'),
            expires_at=now - timedelta(seconds=1),
            attempt_count=0,
            updated_at=now,
            verified_at=None,
            user_id=1,
        )
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=expired.target,
                purpose='LOGIN',
                code='654321',
            )
        self.assertEqual(expired.status, 'EXPIRED')

        blocked = self.manager.create(
            target='blocked@example.com',
            purpose='FORGOT_PASSWORD',
            status='PENDING',
            otp_hash=make_password('654321'),
            expires_at=now + timedelta(minutes=5),
            attempt_count=1,
            updated_at=now,
            verified_at=None,
            user_id=1,
        )
        with self.assertRaises(OtpVerificationError):
            verify_otp(
                target=blocked.target,
                purpose='FORGOT_PASSWORD',
                code='000000',
            )
        self.assertEqual(blocked.status, 'BLOCKED')
        self.assertEqual(blocked.attempt_count, 2)

    @override_settings(
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=1,
        OTP_LIFETIME_SECONDS=300,
        DEFAULT_FROM_EMAIL='test@passbook.invalid',
    )
    def test_resend_rate_limits_and_invalidates_previous_otp(self):
        from .services.otp import OtpRateLimitError, issue_otp

        with patch('users.services.otp.send_email'), patch(
            'users.services.otp.secrets.randbelow',
            side_effect=(111111, 222222),
        ):
            first = issue_otp(
                target='student@example.com',
                channel='EMAIL',
                purpose='CHANGE_EMAIL',
            )
            with self.assertRaises(OtpRateLimitError):
                issue_otp(
                    target='student@example.com',
                    channel='EMAIL',
                    purpose='CHANGE_EMAIL',
                )
            first.updated_at -= timedelta(seconds=61)
            second = issue_otp(
                target='student@example.com',
                channel='EMAIL',
                purpose='CHANGE_EMAIL',
            )
            self.assertEqual(first.status, 'EXPIRED')
            self.assertEqual(second.resend_count, 1)
            second.updated_at -= timedelta(seconds=61)
            with self.assertRaises(OtpRateLimitError):
                issue_otp(
                    target='student@example.com',
                    channel='EMAIL',
                    purpose='CHANGE_EMAIL',
                )

    @override_settings(
        OTP_LIFETIME_SECONDS=300,
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=5,
        DEFAULT_FROM_EMAIL='test@passbook.invalid',
    )
    def test_otp_code_is_not_logged(self):
        from .services.otp import issue_otp

        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger()
        handler = Capture()
        logger.addHandler(handler)
        try:
            with patch('users.services.otp.send_email'), patch(
                'users.services.otp.secrets.randbelow',
                return_value=654321,
            ):
                issue_otp(
                    target='student@example.com',
                    channel='EMAIL',
                    purpose='FORGOT_PASSWORD',
                )
        finally:
            logger.removeHandler(handler)
        self.assertFalse(any(re.search(r'\b654321\b', message) for message in records))


class OtpApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_checkout_phone_otp_send_requires_authenticated_owner_and_hides_code(self):
        from .otp_api_views import OtpRequestView

        user = SimpleNamespace(
            id=71,
            pk=71,
            is_authenticated=True,
            phone='+15550007777',
        )
        request = self.factory.post('/api/auth/resend-otp/', {
            'target': user.phone,
            'purpose': 'CHANGE_PHONE',
        }, format='json')
        force_authenticate(request, user=user)
        duplicate_check = SimpleNamespace(
            exclude=lambda **kwargs: SimpleNamespace(exists=lambda: False),
        )
        with patch.object(
            User.objects,
            'filter',
            return_value=duplicate_check,
        ), patch(
            'users.otp_api_views.issue_otp',
        ) as issue:
            response = OtpRequestView.as_view()(request)
        self.assertEqual(response.status_code, 202)
        self.assertNotIn('otp', response.data)
        issue.assert_called_once_with(
            target=user.phone,
            channel='PHONE',
            purpose='CHANGE_PHONE',
            user=user,
        )

    def test_checkout_phone_otp_send_rejects_unauthenticated_request(self):
        from .otp_api_views import OtpRequestView

        request = self.factory.post('/api/auth/resend-otp/', {
            'target': '+15550007777',
            'purpose': 'CHANGE_PHONE',
        }, format='json')
        with patch('users.otp_api_views.issue_otp') as issue:
            response = OtpRequestView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        issue.assert_not_called()

    def test_register_keeps_success_contract_after_otp_delivery(self):
        from users.api_views import RegisterView

        user = SimpleNamespace(email='student@example.com')
        serializer = Mock()
        serializer.save.return_value = user
        registered_user = Mock()
        registered_user.data = {'email': user.email}
        request = self.factory.post('/api/auth/register/', {
            'name': 'Test Student',
            'email': user.email,
            'password': 'strong-test-password',
        }, format='json')
        unwrapped_post = RegisterView.post.__wrapped__

        with patch.object(RegisterView, 'post', unwrapped_post), patch(
            'users.api_views.RegisterSerializer',
            return_value=serializer,
        ), patch(
            'users.api_views.issue_otp',
        ) as issue, patch(
            'users.api_views.RegisteredUserSerializer',
            return_value=registered_user,
        ):
            response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['verification_required'], True)
        self.assertEqual(response.data['target'], user.email)
        self.assertEqual(response.data['user'], {'email': user.email})
        issue.assert_called_once_with(
            target=user.email,
            channel='EMAIL',
            purpose='REGISTER',
            user=user,
        )

    def test_register_emails_random_hashed_otp_and_verification_activates_user(self):
        from users.api_views import RegisterView
        from users.services.otp import issue_otp
        from users.otp_api_views import OtpVerifyView

        user = SimpleNamespace(
            id=82,
            pk=82,
            email='register@example.test',
            status='PENDING_VERIFICATION',
            save=Mock(),
        )
        serializer = Mock()
        serializer.save.return_value = user
        registered_user = Mock()
        registered_user.data = {'email': user.email}
        user_manager = Mock()
        user_manager.select_for_update.return_value.get.return_value = user
        otp_manager = _OtpManager()
        request = self.factory.post('/api/auth/register/', {
            'name': 'Test Student',
            'email': user.email,
            'password': 'strong-test-password',
        }, format='json')

        with patch.object(RegisterView, 'post', RegisterView.post.__wrapped__), patch(
            'users.api_views.RegisterSerializer',
            return_value=serializer,
        ), patch(
            'users.api_views.RegisteredUserSerializer',
            return_value=registered_user,
        ), patch(
            'users.api_views.issue_otp',
            side_effect=issue_otp,
        ), patch.object(
            User,
            'objects',
            user_manager,
        ), patch.object(
            OtpVerification,
            'objects',
            otp_manager,
        ), patch(
            'users.services.otp.transaction.atomic',
            return_value=nullcontext(),
        ), patch(
            'users.services.otp.secrets.randbelow',
            return_value=271828,
        ), patch(
            'users.services.otp.send_email',
        ) as send_email, patch(
            'users.otp_api_views.get_object_or_404',
            return_value=user,
        ):
            response = RegisterView.as_view()(request)
            self.assertEqual(response.status_code, 202)
            self.assertTrue(response.data['verification_required'])
            self.assertEqual(len(otp_manager.rows), 1)
            verification = otp_manager.rows[0]
            self.assertEqual(verification.status, 'PENDING')
            send_email.assert_called_once()
            email_text = send_email.call_args.kwargs['text']
            code = re.search(r'\b\d{6}\b', email_text).group()
            self.assertTrue(check_password(code, verification.otp_hash))
            self.assertNotEqual(verification.otp_hash, code)

            verify_request = self.factory.post('/api/auth/verify-otp/', {
                'target': user.email,
                'purpose': 'REGISTER',
                'otp': code,
            }, format='json')
            verify_response = OtpVerifyView.as_view()(verify_request)

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.data['user_id'], user.id)
        self.assertEqual(user.status, 'ACTIVE')
        self.assertEqual(verification.status, 'VERIFIED')

    def test_register_returns_service_unavailable_when_otp_delivery_fails(self):
        from users.api_views import RegisterView
        from .services.otp import OtpDeliveryError

        user = SimpleNamespace(email='student@example.com')
        serializer = Mock()
        serializer.save.return_value = user
        request = self.factory.post('/api/auth/register/', {
            'name': 'Test Student',
            'email': user.email,
            'password': 'strong-test-password',
        }, format='json')
        unwrapped_post = RegisterView.post.__wrapped__

        with patch.object(RegisterView, 'post', unwrapped_post), patch(
            'users.api_views.RegisterSerializer',
            return_value=serializer,
        ), patch(
            'users.api_views.issue_otp',
            side_effect=OtpDeliveryError(),
        ):
            response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertNotIn('message', response.data)
        serializer.is_valid.assert_called_once_with(raise_exception=True)

    def test_register_verification_activates_pending_user_without_returning_code(self):
        verification = SimpleNamespace(user_id=42)
        user = SimpleNamespace(
            id=42,
            status='PENDING_VERIFICATION',
            updated_at=None,
            save=lambda update_fields=None: None,
        )
        request = self.factory.post('/api/auth/verify-otp/', {
            'target': 'student@example.com',
            'purpose': 'REGISTER',
            'otp': '654321',
        }, format='json')
        with patch('users.otp_api_views.verify_otp', return_value=verification), patch(
            'users.otp_api_views.get_object_or_404',
            return_value=user,
        ):
            response = OtpVerifyView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.status, 'ACTIVE')
        self.assertNotIn('otp', response.data)

    def test_forgot_password_verification_returns_signed_token_not_code(self):
        verification = SimpleNamespace(user_id=8, id=19)
        request = self.factory.post('/api/auth/verify-otp/', {
            'target': 'student@example.com',
            'purpose': 'FORGOT_PASSWORD',
            'otp': '654321',
        }, format='json')
        with patch('users.otp_api_views.verify_otp', return_value=verification):
            response = OtpVerifyView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('reset_token', response.data)
        self.assertNotIn('otp', response.data)

    def test_login_otp_returns_jwt_only_after_verification(self):
        verification = SimpleNamespace(user_id=12)
        user = SimpleNamespace(id=12, status='ACTIVE')

        class FakeRefresh:
            access_token = 'test-access'

            def __str__(self):
                return 'test-refresh'

        request = self.factory.post('/api/auth/verify-otp/', {
            'target': 'student@example.com',
            'purpose': 'LOGIN',
            'otp': '654321',
        }, format='json')
        with patch('users.otp_api_views.verify_otp', return_value=verification), patch(
            'users.otp_api_views.get_object_or_404',
            return_value=user,
        ), patch(
            'users.otp_api_views.RefreshToken.for_user',
            return_value=FakeRefresh(),
        ), patch(
            'users.serializers.RegisteredUserSerializer',
            return_value=SimpleNamespace(data={'id': 12}),
        ):
            response = OtpVerifyView.as_view()(request)
        self.assertEqual(response.data['access'], 'test-access')
        self.assertEqual(response.data['refresh'], 'test-refresh')
        self.assertNotIn('otp', response.data)

    def test_change_email_and_phone_require_verified_otp(self):
        for purpose, target, field_name in (
            ('CHANGE_EMAIL', 'new@example.com', 'email'),
            ('CHANGE_PHONE', '+15550001111', 'phone'),
        ):
            with self.subTest(purpose=purpose):
                user = SimpleNamespace(
                    id=7,
                    pk=7,
                    is_authenticated=True,
                    email='old@example.com',
                    phone='',
                    updated_at=None,
                    save=lambda update_fields=None: None,
                )
                verification = SimpleNamespace(user_id=user.id, target=target)
                request = self.factory.post('/api/auth/verify-otp/', {
                    'target': target,
                    'purpose': purpose,
                    'otp': '654321',
                }, format='json')
                force_authenticate(request, user=user)
                duplicate_check = SimpleNamespace(
                    exclude=lambda **kwargs: SimpleNamespace(
                        exists=lambda: False,
                    ),
                )
                with patch(
                    'users.otp_api_views.verify_otp',
                    return_value=verification,
                ), patch(
                    'users.otp_api_views.get_object_or_404',
                    return_value=user,
                ), patch.object(
                    User.objects,
                    'filter',
                    return_value=duplicate_check,
                ), patch(
                    'users.otp_api_views.transaction.atomic',
                    return_value=nullcontext(),
                ):
                    response = OtpVerifyView.as_view()(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(getattr(user, field_name), target)

    def test_reset_password_consumes_verified_otp_and_hashes_password(self):
        from .otp_api_views import ResetPasswordView

        verification = SimpleNamespace(
            status='VERIFIED',
            updated_at=None,
            save=lambda update_fields=None: None,
        )
        user = SimpleNamespace(
            id=8,
            email='student@example.com',
            password_hash='old-hash',
            updated_at=None,
            save=lambda update_fields=None: None,
        )
        request = self.factory.post('/api/auth/reset-password/', {
            'reset_token': 'signed-token',
            'new_password': 'N3w-Passbook-Password!',
        }, format='json')
        with patch(
            'users.otp_api_views.signing.loads',
            return_value={'user_id': 8, 'otp_id': 19},
        ), patch(
            'users.otp_api_views.transaction.atomic',
            return_value=nullcontext(),
        ), patch.object(
            OtpVerification.objects,
            'select_for_update',
            return_value=object(),
        ), patch.object(
            User.objects,
            'select_for_update',
            return_value=object(),
        ), patch(
            'users.otp_api_views.get_object_or_404',
            side_effect=(verification, user),
        ), patch('users.otp_api_views.validate_password'):
            response = ResetPasswordView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(check_password('N3w-Passbook-Password!', user.password_hash))
        self.assertEqual(verification.status, 'BLOCKED')

    @override_settings(
        OTP_LIFETIME_SECONDS=300,
        OTP_RESEND_COOLDOWN_SECONDS=60,
        OTP_MAX_RESENDS=5,
        PASSBOOK_SMS_DELIVERY_BACKEND='passbook.tests.send_sms',
        DEFAULT_FROM_EMAIL='test@passbook.invalid',
    )
    def test_each_verification_purpose_can_issue_an_otp(self):
        from .services.otp import issue_otp

        manager = _OtpManager()
        with patch.object(OtpVerification, 'objects', manager), patch(
            'users.services.otp.transaction.atomic',
            return_value=nullcontext(),
        ), patch('users.services.otp.send_email'), patch(
            'users.services.otp.import_string',
            return_value=lambda *args: True,
        ), patch(
            'users.services.otp.secrets.randbelow',
            return_value=987654,
        ):
            for purpose in (
                'REGISTER',
                'LOGIN',
                'FORGOT_PASSWORD',
                'CHANGE_EMAIL',
                'CHANGE_PHONE',
            ):
                with self.subTest(purpose=purpose):
                    target = (
                        '+15550001111'
                        if purpose == 'CHANGE_PHONE'
                        else f'{purpose.lower()}@example.com'
                    )
                    channel = 'PHONE' if purpose == 'CHANGE_PHONE' else 'EMAIL'
                    row = issue_otp(
                        target=target,
                        channel=channel,
                        purpose=purpose,
                    )
                    self.assertEqual(row.purpose, purpose)
                    self.assertTrue(check_password('987654', row.otp_hash))


class AdminPermissionTests(SimpleTestCase):
    def test_only_authenticated_admin_role_is_allowed(self):
        permission = IsAdmin()
        self.assertTrue(permission.has_permission(
            SimpleNamespace(user=SimpleNamespace(
                is_authenticated=True,
                role='ADMIN',
            )),
            view=None,
        ))
        self.assertFalse(permission.has_permission(
            SimpleNamespace(user=SimpleNamespace(
                is_authenticated=True,
                role='STUDENT',
            )),
            view=None,
        ))
        self.assertFalse(permission.has_permission(
            SimpleNamespace(user=SimpleNamespace(
                is_authenticated=False,
                role='ADMIN',
            )),
            view=None,
        ))


class JwtRefreshStatusTests(SimpleTestCase):
    def test_active_accounts_can_refresh(self):
        token = str(RefreshToken.for_user(SimpleNamespace(id=12)))
        manager = SimpleNamespace(exists=lambda: True)
        with patch('users.api_views.User.objects.filter', return_value=manager) as query:
            result = ActiveUserTokenRefreshSerializer().validate({
                'refresh': token,
            })
        query.assert_called_once_with(pk='12', status='ACTIVE')
        self.assertIn('access', result)

    def test_blocked_accounts_cannot_refresh(self):
        token = str(RefreshToken.for_user(SimpleNamespace(id=12)))
        manager = SimpleNamespace(exists=lambda: False)
        with patch('users.api_views.User.objects.filter', return_value=manager):
            with self.assertRaises(AuthenticationFailed):
                ActiveUserTokenRefreshSerializer().validate({
                    'refresh': token,
                })

    def test_revoked_refresh_token_cannot_be_refreshed(self):
        token = RefreshToken.for_user(SimpleNamespace(id=12))
        revoke_token(token)
        with self.assertRaises(AuthenticationFailed):
            ActiveUserTokenRefreshSerializer().validate({'refresh': str(token)})

    def test_logout_revokes_both_access_and_refresh_tokens(self):
        refresh = RefreshToken.for_user(SimpleNamespace(id=12))
        access = refresh.access_token
        request = APIRequestFactory().post('/api/auth/logout/', {
            'refresh': str(refresh),
        }, format='json')
        force_authenticate(
            request,
            user=SimpleNamespace(id=12, is_authenticated=True),
            token=access,
        )

        response = LogoutView.as_view()(request)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(is_token_revoked(access))
        self.assertTrue(is_token_revoked(refresh))


class UserModerationSerializerTests(SimpleTestCase):
    def test_violation_input_requires_reason_and_severity(self):
        serializer = UserViolationInputSerializer(data={
            'violation_type': 'FRAUD',
            'reason': 'Repeated false listing',
            'severity': 'HIGH',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_violation_status_is_controlled_by_admin_workflow(self):
        serializer = UserViolationStatusSerializer(data={'status': 'RESOLVED'})
        self.assertTrue(serializer.is_valid())
        invalid = UserViolationStatusSerializer(data={'status': 'BANNED'})
        self.assertFalse(invalid.is_valid())

    def test_account_status_accepts_only_schema_values(self):
        serializer = UserAccountStatusSerializer(data={'status': 'BLOCKED'})
        self.assertTrue(serializer.is_valid())
        invalid = UserAccountStatusSerializer(data={'status': 'DELETED'})
        self.assertFalse(invalid.is_valid())


class UserAddressAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(id=10, is_authenticated=True)

    def test_user_cannot_patch_or_delete_another_users_address(self):
        for method in ('patch', 'delete'):
            with self.subTest(method=method):
                request = (
                    self.factory.patch('/api/users/addresses/52/', {'label': 'Home'})
                    if method == 'patch'
                    else self.factory.delete('/api/users/addresses/52/')
                )
                force_authenticate(request, user=self.user)
                with patch(
                    'users.api_views.get_object_or_404',
                    side_effect=Http404,
                ) as get_address:
                    response = UserAddressDetailView.as_view()(
                        request,
                        address_id=52,
                    )

                self.assertEqual(response.status_code, 404)
                get_address.assert_called_once_with(
                    UserAddress,
                    pk=52,
                    user=self.user,
                )

    def test_anonymous_user_cannot_list_or_create_addresses(self):
        get_response = UserAddressListCreateView.as_view()(
            self.factory.get('/api/users/addresses/'),
        )
        post_response = UserAddressListCreateView.as_view()(
            self.factory.post('/api/users/addresses/', {}, format='json'),
        )

        self.assertEqual(get_response.status_code, 401)
        self.assertEqual(post_response.status_code, 401)

# Create your tests here.
