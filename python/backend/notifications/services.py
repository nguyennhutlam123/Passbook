import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notification


logger = logging.getLogger(__name__)


def create_notification(
    user_id,
    *,
    notification_type,
    title,
    content,
    entity_type=None,
    entity_id=None,
    created_at=None,
):
    return Notification.objects.create(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        content=content,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
        created_at=created_at or timezone.now(),
    )


def notify_borrow_order_parties(
    borrow_order,
    *,
    title,
    content,
    recipient_ids=None,
    created_at=None,
):
    recipients = (
        recipient_ids
        if recipient_ids is not None
        else (borrow_order.borrower_id, borrow_order.lender_id)
    )
    seen = set()
    for user_id in recipients:
        if user_id is None or user_id in seen:
            continue
        seen.add(user_id)
        create_notification(
            user_id,
            notification_type='BORROW_ORDER',
            title=title,
            content=content,
            entity_type='BORROW_ORDER',
            entity_id=borrow_order.id,
            created_at=created_at,
        )


def notify_order_parties(order, *, title, content):
    recipients = []
    seen = set()
    for user in (order.buyer, order.seller):
        if user is None or user.id in seen:
            continue
        seen.add(user.id)
        create_notification(
            user.id,
            notification_type='ORDER',
            title=title,
            content=content,
            entity_type='ORDER',
            entity_id=order.id,
        )
        if user.email:
            recipients.append((user.email, user.full_name))

    if recipients:
        transaction.on_commit(
            lambda: _send_order_email(
                order.order_code,
                order.status,
                title,
                content,
                tuple(recipients),
            ),
        )


def notify_order_status_changed(order, previous_status):
    if order.status == previous_status:
        return
    notify_order_parties(
        order,
        title=f'Cập nhật đơn hàng {order.order_code}',
        content=(
            f'Trạng thái đơn hàng của bạn đã được cập nhật từ '
            f'{previous_status} thành {order.status}.'
        ),
    )


def _send_order_email(order_code, order_status, subject, content, recipients):
    if (
        settings.EMAIL_BACKEND.endswith('.smtp.EmailBackend')
        and (not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD)
    ):
        logger.error(
            'Order email not sent: SMTP credentials are not configured '
            '(order_code=%s, recipient_count=%d).',
            order_code,
            len(recipients),
        )
        return

    failures = []
    message = (
        f'{content}\n\nMã đơn: {order_code}\nTrạng thái hiện tại: {order_status}\n'
        'Đăng nhập PassBook để xem chi tiết đơn hàng.'
    )
    for email, _name in recipients:
        try:
            sent = send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException):
            logger.exception(
                'Order email delivery failed (order_code=%s).',
                order_code,
            )
            continue
        if sent != 1:
            failures.append(email)
    if failures:
        logger.error(
            'Order email backend did not accept all messages '
            '(order_code=%s, failed_count=%d).',
            order_code,
            len(failures),
        )
