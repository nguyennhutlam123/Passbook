import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils import timezone
from django.utils.module_loading import import_string

from users.models import OtpVerification, User


class OtpVerificationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Mã xác minh không hợp lệ hoặc đã hết hạn.'
    default_code = 'invalid_otp'


class OtpRateLimitError(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Vui lòng chờ trước khi yêu cầu mã mới.'
    default_code = 'otp_rate_limited'


class OtpDeliveryError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Không thể gửi mã xác minh.'
    default_code = 'otp_delivery_unavailable'


def issue_otp(*, target, channel, purpose, user=None):
    now = timezone.now()
    target = target.strip().lower() if channel == 'EMAIL' else target.strip()
    expires_in = timedelta(seconds=settings.OTP_LIFETIME_SECONDS)

    with transaction.atomic():
        if user is not None:
            user = User.objects.select_for_update().get(pk=user.pk)
        previous = (
            OtpVerification.objects.select_for_update()
            .filter(target=target, purpose=purpose)
            .order_by('-created_at', '-id')
            .first()
        )
        resend_count = 0
        if previous is not None:
            within_window = (
                now - previous.created_at
            ).total_seconds() < settings.OTP_RESEND_WINDOW_SECONDS
            if within_window:
                cooldown_until = previous.updated_at + timedelta(
                    seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
                )
                if now < cooldown_until:
                    raise OtpRateLimitError('Vui lòng chờ trước khi yêu cầu mã mới.')
                if previous.resend_count >= settings.OTP_MAX_RESENDS:
                    raise OtpRateLimitError('Đã vượt quá số lần yêu cầu mã.')
                resend_count = previous.resend_count + 1
            if previous.status == 'PENDING':
                previous.status = 'EXPIRED'
                previous.updated_at = now
                previous.save(update_fields=['status', 'updated_at'])

        code = f'{secrets.randbelow(1_000_000):06d}'
        verification = OtpVerification.objects.create(
            user=user,
            channel=channel,
            purpose=purpose,
            target=target,
            otp_hash=make_password(code),
            expires_at=now + expires_in,
            attempt_count=0,
            resend_count=resend_count,
            status='PENDING',
            created_at=now,
            updated_at=now,
        )
        _deliver_otp(target=target, channel=channel, purpose=purpose, code=code)

    return verification


def verify_otp(*, target, purpose, code, user_id=None):
    now = timezone.now()
    target = target.strip().lower() if '@' in target else target.strip()
    error = None
    verification = None
    with transaction.atomic():
        query = (
            OtpVerification.objects.select_for_update()
            .filter(target=target, purpose=purpose, status='PENDING')
        )
        if user_id is not None:
            query = query.filter(user_id=user_id)
        verification = query.order_by('-created_at', '-id').first()
        if verification is None:
            error = OtpVerificationError('Mã xác minh không hợp lệ hoặc đã hết hạn.')
        elif verification.expires_at <= now:
            verification.status = 'EXPIRED'
            verification.updated_at = now
            verification.save(update_fields=['status', 'updated_at'])
            error = OtpVerificationError('Mã xác minh không hợp lệ hoặc đã hết hạn.')
        elif verification.attempt_count >= settings.OTP_MAX_ATTEMPTS:
            verification.status = 'BLOCKED'
            verification.updated_at = now
            verification.save(update_fields=['status', 'updated_at'])
            error = OtpVerificationError('Mã xác minh không hợp lệ hoặc đã hết hạn.')
        elif not check_password(code, verification.otp_hash):
            verification.attempt_count += 1
            if verification.attempt_count >= settings.OTP_MAX_ATTEMPTS:
                verification.status = 'BLOCKED'
            verification.updated_at = now
            verification.save(update_fields=[
                'attempt_count', 'status', 'updated_at',
            ])
            error = OtpVerificationError('Mã xác minh không hợp lệ hoặc đã hết hạn.')
        else:
            verification.status = 'VERIFIED'
            verification.verified_at = now
            verification.updated_at = now
            verification.save(update_fields=[
                'status', 'verified_at', 'updated_at',
            ])

    if error is not None:
        raise error
    return verification


def _deliver_otp(*, target, channel, purpose, code):
    subject = 'Mã xác minh Passbook'
    message = (
        f'Mã xác minh Passbook của bạn là {code}. '
        f'Mã sẽ hết hạn sau {settings.OTP_LIFETIME_SECONDS // 60} phút.'
    )
    if channel == 'EMAIL':
        try:
            sent = send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [target],
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException) as exc:
            raise OtpDeliveryError('Không thể gửi mã xác minh.') from exc
        if sent != 1:
            raise OtpDeliveryError('Không thể gửi mã xác minh.')
        return

    backend_path = settings.PASSBOOK_SMS_DELIVERY_BACKEND
    if not backend_path:
        raise OtpDeliveryError('Kênh SMS chưa được cấu hình.')
    try:
        sender = import_string(backend_path)
    except (ImportError, AttributeError) as exc:
        raise OtpDeliveryError('Kênh SMS chưa được cấu hình hợp lệ.') from exc
    if sender(target, code, purpose) is False:
        raise OtpDeliveryError('Không thể gửi mã xác minh.')
