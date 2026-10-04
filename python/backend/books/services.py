import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from notifications.models import Notification

from .models import (
    Book,
    BookReservation,
    BorrowOrder,
    LendListing,
    Order,
    Payment,
    Refund,
)


MONEY_QUANTUM = Decimal('0.0001')


class PaymentProviderUnavailable(Exception):
    pass


class PaymentProvider(ABC):
    @abstractmethod
    def create_payment_intent(self, idempotency_key, amount, currency):
        raise NotImplementedError

    @abstractmethod
    def create_refund_intent(self, idempotency_key, payment_reference, amount, currency):
        raise NotImplementedError


class FakePaymentProvider(PaymentProvider):
    name = 'fake'

    def create_payment_intent(self, idempotency_key, amount, currency):
        payload = f'{idempotency_key}:{amount}:{currency}'.encode()
        reference = hashlib.sha256(payload).hexdigest()[:32]
        return f'fake_{reference}'

    def create_refund_intent(self, idempotency_key, payment_reference, amount, currency):
        payload = f'{idempotency_key}:{payment_reference}:{amount}:{currency}'.encode()
        reference = hashlib.sha256(payload).hexdigest()[:32]
        return f'fake_refund_{reference}'

    @staticmethod
    def transition(current_status, target_status):
        allowed = {
            'PENDING': {'PAID', 'FAILED', 'CANCELLED'},
            'FAILED': {'PENDING'},
        }
        if current_status == target_status:
            return target_status
        if target_status not in allowed.get(current_status, set()):
            raise ValidationError(
                f'Không thể chuyển thanh toán từ {current_status} sang {target_status}.',
            )
        return target_status


def get_payment_provider(provider_name):
    if provider_name == FakePaymentProvider.name:
        if not fake_payments_enabled():
            raise PaymentProviderUnavailable('Fake payment provider chỉ khả dụng trong local/test.')
        return FakePaymentProvider()
    raise PaymentProviderUnavailable(f'Payment provider "{provider_name}" chưa được cấu hình.')


def fake_payments_enabled():
    return (
        settings.PASSBOOK_ENVIRONMENT in ('local', 'test')
        and settings.PASSBOOK_FAKE_PAYMENTS_ENABLED
    )


@transaction.atomic
def transition_fake_payment(payment_id, target_status):
    payment_reference = get_object_or_404(
        Payment.objects.only('order_id'),
        pk=payment_id,
    )
    order = Order.objects.select_for_update().get(pk=payment_reference.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    payment.order = order
    provider = get_payment_provider(payment.provider)
    if not isinstance(provider, FakePaymentProvider):
        raise PaymentProviderUnavailable('Không thể mô phỏng provider này.')
    target_status = provider.transition(payment.status, target_status)
    if target_status == payment.status:
        return payment
    if target_status == 'PAID':
        if payment.order.status != 'PENDING_PAYMENT':
            raise ValidationError('Đơn hàng không còn chờ thanh toán.')
        if Payment.objects.select_for_update().filter(
            order=payment.order,
            status='PAID',
        ).exists():
            raise ValidationError('Đơn hàng đã có khoản thanh toán thành công.')

    now = timezone.now()
    payment.status = target_status
    payment.updated_at = now
    fields = ['status', 'updated_at']
    if target_status == 'PAID':
        payment.paid_at = now
        fields.append('paid_at')
        payment.order.status = 'CONFIRMED'
        payment.order.updated_at = now
        payment.order.save(update_fields=['status', 'updated_at'])
    payment.save(update_fields=fields)
    return payment


@transaction.atomic
def transition_fake_refund(refund_id, target_status):
    refund = get_object_or_404(
        Refund.objects.select_for_update().select_related('payment'),
        pk=refund_id,
    )
    refund.payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    provider = get_payment_provider(refund.provider)
    if not isinstance(provider, FakePaymentProvider):
        raise PaymentProviderUnavailable('Không thể mô phỏng provider này.')
    if target_status not in ('COMPLETED', 'FAILED'):
        raise ValidationError('Trạng thái hoàn tiền mô phỏng không hợp lệ.')
    if refund.status == target_status:
        return refund
    if refund.status not in ('REQUESTED', 'FAILED'):
        raise ValidationError(
            f'Không thể chuyển hoàn tiền từ {refund.status} sang {target_status}.',
        )
    if target_status == 'COMPLETED' and refund.payment.status not in ('PAID', 'REFUNDED'):
        raise ValidationError('Chỉ có thể hoàn tiền cho khoản thanh toán đã thành công.')

    now = timezone.now()
    refund.status = target_status
    refund.updated_at = now
    fields = ['status', 'updated_at']
    if target_status == 'COMPLETED':
        refund.completed_at = now
        refund.provider_refund_reference = provider.create_refund_intent(
            refund.idempotency_key,
            refund.payment.provider_transaction_code or str(refund.payment_id),
            refund.amount,
            refund.currency,
        )
        fields.extend(('completed_at', 'provider_refund_reference'))
        previous_refunds = Refund.objects.select_for_update().filter(
            payment=refund.payment,
            status='COMPLETED',
        ).exclude(pk=refund.pk).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if previous_refunds + refund.amount > refund.payment.amount:
            raise ValidationError('Tổng các khoản hoàn vượt quá số tiền đã thanh toán.')
        if previous_refunds + refund.amount >= refund.payment.amount:
            refund.payment.status = 'REFUNDED'
            refund.payment.updated_at = now
            refund.payment.save(update_fields=['status', 'updated_at'])
    refund.save(update_fields=fields)
    return refund


def calculate_payment_split(amount, fee_rate):
    try:
        amount = Decimal(amount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        fee_rate = Decimal(fee_rate)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Số tiền hoặc tỷ lệ phí không hợp lệ.') from exc
    if amount <= 0:
        raise ValidationError('Số tiền phải lớn hơn 0.')
    if fee_rate < 0 or fee_rate > 1:
        raise ValidationError('Tỷ lệ phí phải nằm trong khoảng 0 đến 1.')
    fee = (amount * fee_rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return {
        'amount': amount,
        'platform_fee_rate': fee_rate,
        'platform_fee': fee,
        'seller_amount': amount - fee,
    }


def _notify(user_id, notification_type, title, content, entity_type, entity_id, now):
    Notification.objects.create(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        content=content,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
        created_at=now,
    )


@transaction.atomic
def transition_reservation(reservation_id, actor, action):
    reservation = (
        BookReservation.objects
        .select_for_update()
        .get(pk=reservation_id)
    )
    reservation.book = Book.objects.select_for_update().get(pk=reservation.book_id)
    if action in ('confirm', 'reject') and actor.id != reservation.owner_id:
        raise PermissionDenied('Chỉ chủ sách mới được xử lý yêu cầu đặt sách.')
    if action == 'cancel' and actor.id != reservation.requester_id:
        raise PermissionDenied('Chỉ người yêu cầu mới được hủy đặt sách.')
    if action == 'complete' and actor.id not in (
        reservation.requester_id,
        reservation.owner_id,
    ):
        raise PermissionDenied('Bạn không tham gia yêu cầu đặt sách này.')
    if action not in ('confirm', 'reject', 'cancel', 'complete'):
        raise ValidationError('Thao tác đặt sách không hợp lệ.')

    now = timezone.now()
    lend_listing = (
        LendListing.objects
        .select_for_update()
        .filter(
            book_id=reservation.book_id,
            status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
        )
        .order_by('-created_at', '-id')
        .first()
    )
    is_borrow = lend_listing is not None
    active_listing = None
    if not is_borrow:
        active_listing = (
            reservation.book.sale_listings
            .select_for_update()
            .filter(status__in=('ACTIVE', 'RESERVED'))
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .order_by('-created_at', '-id')
            .first()
        )
    expires = reservation.status == 'PENDING' or (
        reservation.status == 'CONFIRMED' and not is_borrow
    )
    if expires and reservation.expires_at <= now:
        reservation.status = 'EXPIRED'
        reservation.updated_at = now
        reservation.save(update_fields=['status', 'updated_at'])
        reservation.book.sale_listings.filter(status='RESERVED').update(
            status='ACTIVE',
            updated_at=now,
        )
        if reservation.book.status == 'RESERVED':
            reservation.book.status = 'AVAILABLE'
            reservation.book.updated_at = now
            reservation.book.save(update_fields=['status', 'updated_at'])
        if is_borrow and lend_listing.status == 'RESERVED':
            lend_listing.status = 'ACTIVE'
            lend_listing.updated_at = now
            lend_listing.save(update_fields=['status', 'updated_at'])

    if action in ('confirm', 'reject'):
        if reservation.status != 'PENDING':
            raise ValidationError('Chỉ yêu cầu đang chờ mới có thể xác nhận hoặc từ chối.')
        if action == 'confirm':
            if is_borrow:
                if lend_listing.status != 'RESERVED':
                    raise ValidationError('Tin cho mượn không còn được giữ cho yêu cầu này.')
            elif active_listing is None or active_listing.status != 'ACTIVE':
                raise ValidationError('Tin đăng không còn khả dụng để xác nhận đặt sách.')
        reservation.status = 'CONFIRMED' if action == 'confirm' else 'REJECTED'
        if action == 'confirm':
            reservation.book.status = 'ON_LOAN' if is_borrow else 'RESERVED'
            reservation.book.updated_at = now
            reservation.book.save(update_fields=['status', 'updated_at'])
            if is_borrow:
                lend_listing.status = 'ON_LOAN'
                lend_listing.updated_at = now
                lend_listing.save(update_fields=['status', 'updated_at'])
            else:
                active_listing.status = 'RESERVED'
                active_listing.updated_at = now
                active_listing.save(update_fields=['status', 'updated_at'])
        recipient_id = reservation.requester_id
    elif action == 'cancel':
        allowed_statuses = ('PENDING',) if is_borrow else ('PENDING', 'CONFIRMED')
        if reservation.status not in allowed_statuses:
            raise ValidationError('Yêu cầu này không thể hủy ở trạng thái hiện tại.')
        reservation.status = 'CANCELLED'
        recipient_id = reservation.owner_id
    elif action == 'complete':
        if reservation.status != 'CONFIRMED':
            raise ValidationError('Chỉ yêu cầu đã xác nhận mới có thể hoàn tất.')
        reservation.status = 'COMPLETED'
        recipient_id = (
            reservation.owner_id
            if actor.id == reservation.requester_id
            else reservation.requester_id
        )
    else:
        raise ValidationError('Thao tác đặt sách không hợp lệ.')

    reservation.updated_at = now
    reservation.save(update_fields=['status', 'updated_at'])
    if reservation.status in ('CANCELLED', 'REJECTED', 'COMPLETED'):
        reservation.book.sale_listings.filter(status='RESERVED').update(
            status='ACTIVE',
            updated_at=now,
        )
        if reservation.book.status in ('RESERVED', 'ON_LOAN'):
            reservation.book.status = 'AVAILABLE'
            reservation.book.updated_at = now
            reservation.book.save(update_fields=['status', 'updated_at'])
        if is_borrow and lend_listing.status in ('RESERVED', 'ON_LOAN'):
            lend_listing.status = 'ACTIVE'
            lend_listing.updated_at = now
            lend_listing.save(update_fields=['status', 'updated_at'])
    _notify(
        recipient_id,
        'BOOK_RESERVATION',
        'Cập nhật yêu cầu đặt sách',
        f'Yêu cầu đặt sách #{reservation.id} đã chuyển sang {reservation.status}.',
        'BOOK_RESERVATION',
        reservation.id,
        now,
    )
    return reservation


@transaction.atomic
def transition_borrow_order(borrow_order_id, actor, action):
    borrow_order = (
        BorrowOrder.objects
        .select_for_update()
        .select_related('order', 'lend_listing', 'lend_listing__book')
        .get(pk=borrow_order_id)
    )
    now = timezone.now()
    if action in ('confirm', 'reject', 'ready'):
        if actor.id != borrow_order.lender_id:
            raise PermissionDenied('Chỉ bên cho mượn mới được thực hiện thao tác này.')
    if action == 'confirm':
        _require_borrow_status(borrow_order, 'PENDING')
        borrow_order.status = 'CONFIRMED'
        recipient_id = borrow_order.borrower_id
    elif action == 'reject':
        _require_borrow_status(borrow_order, 'PENDING')
        borrow_order.status = 'REJECTED'
        borrow_order.order.status = 'CANCELLED'
        borrow_order.order.updated_at = now
        borrow_order.order.save(update_fields=['status', 'updated_at'])
        borrow_order.lend_listing.status = 'ACTIVE'
        borrow_order.lend_listing.updated_at = now
        borrow_order.lend_listing.save(update_fields=['status', 'updated_at'])
        if borrow_order.lend_listing.book.status == 'RESERVED':
            borrow_order.lend_listing.book.status = 'AVAILABLE'
            borrow_order.lend_listing.book.updated_at = now
            borrow_order.lend_listing.book.save(update_fields=['status', 'updated_at'])
        recipient_id = borrow_order.borrower_id
    elif action == 'ready':
        _require_borrow_status(borrow_order, 'CONFIRMED')
        if not borrow_order.order.payments.filter(status='PAID').exists():
            raise ValidationError('Chỉ có thể chuẩn bị sách sau khi thanh toán được xác nhận.')
        borrow_order.status = 'READY_FOR_PICKUP'
        recipient_id = borrow_order.borrower_id
    elif action == 'start':
        if actor.id != borrow_order.borrower_id:
            raise PermissionDenied('Chỉ người mượn mới có thể xác nhận đã nhận sách.')
        _require_borrow_status(borrow_order, 'READY_FOR_PICKUP')
        borrow_order.status = 'ACTIVE'
        borrow_order.actual_start_at = now
        borrow_order.lend_listing.status = 'ON_LOAN'
        borrow_order.lend_listing.updated_at = now
        borrow_order.lend_listing.book.status = 'ON_LOAN'
        borrow_order.lend_listing.book.updated_at = now
        borrow_order.lend_listing.book.save(update_fields=['status', 'updated_at'])
        borrow_order.lend_listing.save(update_fields=['status', 'updated_at'])
        recipient_id = borrow_order.lender_id
    elif action == 'request_return':
        if actor.id not in (borrow_order.borrower_id, borrow_order.lender_id):
            raise PermissionDenied('Bạn không tham gia yêu cầu mượn sách này.')
        if borrow_order.status not in ('ACTIVE', 'OVERDUE'):
            raise ValidationError('Chỉ sách đang được mượn mới có thể yêu cầu trả.')
        borrow_order.status = 'RETURN_REQUESTED'
        borrow_order.return_status = 'REQUESTED'
        borrow_order.return_requested_by = actor
        borrow_order.return_requested_at = now
        recipient_id = (
            borrow_order.lender_id
            if actor.id == borrow_order.borrower_id
            else borrow_order.borrower_id
        )
    elif action == 'return':
        if actor.id not in (borrow_order.borrower_id, borrow_order.lender_id):
            raise PermissionDenied('Bạn không tham gia yêu cầu mượn sách này.')
        if borrow_order.status != 'RETURN_REQUESTED':
            raise ValidationError('Sách chưa có yêu cầu trả đang chờ.')
        if actor.id == getattr(borrow_order.return_requested_by, 'id', None):
            raise PermissionDenied('Bên còn lại cần xác nhận đã nhận lại sách.')
        borrow_order.status = 'RETURNED'
        borrow_order.return_status = 'COMPLETED'
        borrow_order.return_approved_at = now
        borrow_order.actual_return_at = now
        borrow_order.lend_listing.status = 'ACTIVE'
        borrow_order.lend_listing.updated_at = now
        borrow_order.lend_listing.book.status = 'AVAILABLE'
        borrow_order.lend_listing.book.updated_at = now
        borrow_order.lend_listing.book.save(update_fields=['status', 'updated_at'])
        borrow_order.lend_listing.save(update_fields=['status', 'updated_at'])
        recipient_id = (
            borrow_order.lender_id
            if actor.id == borrow_order.borrower_id
            else borrow_order.borrower_id
        )
    elif action == 'complete':
        if actor.id not in (borrow_order.borrower_id, borrow_order.lender_id):
            raise PermissionDenied('Bạn không tham gia yêu cầu mượn sách này.')
        _require_borrow_status(borrow_order, 'RETURNED')
        borrow_order.status = 'COMPLETED'
        borrow_order.order.status = 'COMPLETED'
        borrow_order.order.completed_at = now
        borrow_order.order.updated_at = now
        borrow_order.order.save(update_fields=['status', 'completed_at', 'updated_at'])
        recipient_id = (
            borrow_order.lender_id
            if actor.id == borrow_order.borrower_id
            else borrow_order.borrower_id
        )
    elif action == 'cancel':
        if actor.id != borrow_order.borrower_id:
            raise PermissionDenied('Chỉ người mượn mới được hủy yêu cầu.')
        _require_borrow_status(borrow_order, 'PENDING')
        borrow_order.status = 'CANCELLED'
        borrow_order.order.status = 'CANCELLED'
        borrow_order.order.updated_at = now
        borrow_order.order.save(update_fields=['status', 'updated_at'])
        borrow_order.lend_listing.status = 'ACTIVE'
        borrow_order.lend_listing.updated_at = now
        borrow_order.lend_listing.save(update_fields=['status', 'updated_at'])
        if borrow_order.lend_listing.book.status == 'RESERVED':
            borrow_order.lend_listing.book.status = 'AVAILABLE'
            borrow_order.lend_listing.book.updated_at = now
            borrow_order.lend_listing.book.save(update_fields=['status', 'updated_at'])
        recipient_id = borrow_order.lender_id
    else:
        raise ValidationError('Thao tác mượn sách không hợp lệ.')

    borrow_order.updated_at = now
    borrow_order.save()
    _notify(
        recipient_id,
        'BORROW_ORDER',
        'Cập nhật yêu cầu mượn sách',
        f'Yêu cầu mượn sách #{borrow_order.id} đã chuyển sang {borrow_order.status}.',
        'BORROW_ORDER',
        borrow_order.id,
        now,
    )
    return borrow_order


def _require_borrow_status(borrow_order, expected):
    if borrow_order.status != expected:
        raise ValidationError(
            f'Thao tác này chỉ hợp lệ khi yêu cầu ở trạng thái {expected}.',
        )
