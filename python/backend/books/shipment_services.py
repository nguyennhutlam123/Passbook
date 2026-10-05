from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.services import notify_order_status_changed

from .models import BorrowOrder, Payment, Shipment, ShipmentTracking


SHIPMENT_TRANSITIONS = {
    'PENDING': {'PICKED_UP'},
    'SHIPPED': {'PICKED_UP', 'IN_TRANSIT'},
    'PICKED_UP': {'IN_TRANSIT', 'EXCEPTION'},
    'IN_TRANSIT': {'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION', 'RETURNED'},
    'OUT_FOR_DELIVERY': {'DELIVERED', 'EXCEPTION', 'RETURNED'},
    'EXCEPTION': {'IN_TRANSIT', 'RETURNED'},
}
SHIPMENT_STATUSES = (
    'PENDING',
    'SHIPPED',
    'PICKED_UP',
    'IN_TRANSIT',
    'OUT_FOR_DELIVERY',
    'DELIVERED',
    'EXCEPTION',
    'RETURNED',
)


def is_return_shipment(shipment, borrow=None):
    if borrow is None:
        borrow = BorrowOrder.objects.filter(order_id=shipment.order_id).first()
    return bool(
        borrow
        and borrow.return_tracking_code
        and borrow.return_tracking_code == shipment.tracking_code
    )


def validate_shipment_transition(old_status, new_status):
    if new_status not in SHIPMENT_TRANSITIONS.get(old_status, set()):
        raise ValidationError(
            f'Không thể chuyển Shipment từ {old_status} sang {new_status}.',
        )


def create_pending_shipment(
    order,
    *,
    changed_by=None,
    carrier=None,
    tracking_code=None,
    location=None,
    description='Đã tạo thông tin vận chuyển; chờ PassBook tiếp nhận xử lý.',
    created_at=None,
):
    now = created_at or timezone.now()
    shipment = Shipment.objects.create(
        order=order,
        carrier=carrier,
        tracking_code=tracking_code,
        shipping_fee=Decimal('0'),
        status='PENDING',
        shipped_at=None,
        currency=order.currency,
        created_at=now,
        updated_at=now,
    )
    ShipmentTracking.objects.create(
        shipment=shipment,
        status='PENDING',
        source='SYSTEM',
        changed_by_id=getattr(changed_by, 'id', None),
        location=location,
        description=description,
        occurred_at=now,
        created_at=now,
    )
    return shipment


@transaction.atomic
def update_shipment_status(
    shipment,
    *,
    status,
    source,
    changed_by=None,
    borrow=None,
    location=None,
    description=None,
    occurred_at=None,
    event_model=ShipmentTracking,
):
    old_status = shipment.status
    validate_shipment_transition(old_status, status)

    now = timezone.now()
    occurred_at = occurred_at or now
    latest = shipment.tracking_events.order_by(
        '-occurred_at',
        '-id',
    ).first()
    if latest is not None and occurred_at < latest.occurred_at:
        raise ValidationError(
            {'occurred_at': 'Thời điểm sự kiện không được trước sự kiện gần nhất.'},
        )
    actor_id = getattr(changed_by, 'id', None)

    event = event_model.objects.create(
        shipment=shipment,
        status=status,
        source=source,
        changed_by_id=actor_id,
        location=location,
        description=description,
        occurred_at=occurred_at,
        created_at=now,
    )
    shipment.status = status
    if status == 'PICKED_UP' and shipment.shipped_at is None:
        shipment.shipped_at = occurred_at
    if status == 'DELIVERED':
        shipment.delivered_at = occurred_at
    shipment.updated_at = now
    shipment.save(update_fields=[
        'status',
        'shipped_at',
        'delivered_at',
        'updated_at',
    ])

    order = getattr(shipment, 'order', None)
    is_borrow_order = (
        order is not None
        and getattr(order, 'order_type', None) == 'BORROW'
    )
    if status == 'PICKED_UP' and is_borrow_order:
        if order.status not in ('CONFIRMED', 'PROCESSING'):
            raise ValidationError(
                f'Không thể giao BORROW Order ở trạng thái {order.status}.',
            )
        if order.status == 'CONFIRMED':
            previous_order_status = order.status
            order.status = 'PROCESSING'
            order.updated_at = now
            order.save(update_fields=['status', 'updated_at'])
            notify_order_status_changed(order, previous_order_status)

    if status == 'DELIVERED' and is_return_shipment(shipment, borrow):
        borrow.status = 'RETURNED'
        borrow.return_status = 'DELIVERED'
        borrow.updated_at = now
        borrow.save(update_fields=['status', 'return_status', 'updated_at'])
    elif status == 'DELIVERED' and is_borrow_order:
        if borrow is None or borrow.status not in ('CONFIRMED', 'READY_FOR_PICKUP'):
            raise ValidationError(
                'Phiếu mượn chưa ở trạng thái có thể giao.',
            )
        if order.status not in ('CONFIRMED', 'PROCESSING'):
            raise ValidationError(
                f'Không thể giao BORROW Order ở trạng thái {order.status}.',
            )
        borrow.status = 'ACTIVE'
        borrow.actual_start_at = occurred_at
        borrow.updated_at = now
        borrow.save(update_fields=['status', 'actual_start_at', 'updated_at'])
        listing = borrow.lend_listing
        listing.status = 'ON_LOAN'
        listing.updated_at = now
        listing.save(update_fields=['status', 'updated_at'])
        listing.book.status = 'ON_LOAN'
        listing.book.updated_at = now
        listing.book.save(update_fields=['status', 'updated_at'])
        for payment in Payment.objects.select_for_update().filter(order_id=order.id):
            if payment.payment_method == 'COD' and payment.status != 'PAID':
                payment.status = 'PAID'
                payment.paid_at = now
                payment.updated_at = now
                payment.save(update_fields=['status', 'paid_at', 'updated_at'])
        if order.status == 'CONFIRMED':
            previous_order_status = order.status
            order.status = 'PROCESSING'
            order.updated_at = now
            order.save(update_fields=['status', 'updated_at'])
            notify_order_status_changed(order, previous_order_status)
    elif status == 'DELIVERED':
        if order is not None and getattr(order, 'order_type', None) == 'SALE':
            if order.status not in ('CONFIRMED', 'PROCESSING'):
                raise ValidationError(
                    f'Không thể hoàn tất SALE Order ở trạng thái {order.status}.',
                )
            remaining_shipments = Shipment.objects.filter(
                order_id=order.id,
            ).exclude(status='DELIVERED')
            if not remaining_shipments.exists():
                for payment in Payment.objects.select_for_update().filter(order_id=order.id):
                    if payment.payment_method == 'COD' and payment.status != 'PAID':
                        payment.status = 'PAID'
                        payment.paid_at = now
                        payment.updated_at = now
                        payment.save(update_fields=['status', 'paid_at', 'updated_at'])
                previous_order_status = order.status
                order.status = 'COMPLETED'
                order.completed_at = now
                order.updated_at = now
                order.save(update_fields=['status', 'completed_at', 'updated_at'])
                notify_order_status_changed(order, previous_order_status)
    return event, old_status
