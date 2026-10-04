from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin

from .commerce_api_views import BookPagination, BorrowOrderListView
from .models import (
    BookImage,
    BookReservation,
    BorrowOrder,
    LendListing,
    Order,
    Payment,
    Refund,
    SaleOrderItem,
    Shipment,
    ShipmentTracking,
)
from notifications.services import notify_order_status_changed
from .shipment_services import (
    SHIPMENT_STATUSES,
    SHIPMENT_TRANSITIONS,
    is_return_shipment,
    update_shipment_status,
)


def _apply_admin_filters(queryset, request, *, borrow=False):
    params = request.query_params
    status_value = params.get('status', '').strip().upper()
    if status_value:
        valid_statuses = (
            {value for value, _label in BorrowOrder.STATUS_CHOICES}
            if borrow else
            {value for value, _label in BookReservation.STATUS_CHOICES}
        )
        if status_value not in valid_statuses:
            raise ValidationError({
                'status': 'Trạng thái không hợp lệ.',
            })
        queryset = queryset.filter(status=status_value)

    user_id = params.get('user')
    if user_id:
        try:
            user_id = int(user_id)
            if user_id < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValidationError({'user': 'User ID phải là số nguyên dương.'}) from exc
        queryset = queryset.filter(
            Q(borrower_id=user_id) | Q(lender_id=user_id)
            if borrow
            else Q(requester_id=user_id) | Q(owner_id=user_id)
        )

    book_id = params.get('book')
    if book_id:
        try:
            book_id = int(book_id)
            if book_id < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValidationError({'book': 'Book ID phải là số nguyên dương.'}) from exc
        queryset = (
            queryset.filter(lend_listing__book_id=book_id)
            if borrow else queryset.filter(book_id=book_id)
        )

    listing_id = params.get('listing')
    if listing_id:
        try:
            listing_id = int(listing_id)
            if listing_id < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValidationError({'listing': 'Listing ID phải là số nguyên dương.'}) from exc
        if borrow:
            queryset = queryset.filter(lend_listing_id=listing_id)
        else:
            queryset = queryset.filter(
                Q(book__sale_listings__id=listing_id)
                | Q(book__lend_listings__id=listing_id),
            ).distinct()

    start_date = _parse_filter_date(params.get('start_date'), 'start_date')
    end_date = _parse_filter_date(params.get('end_date'), 'end_date')
    if start_date and end_date and start_date > end_date:
        raise ValidationError({'end_date': 'End date không được trước start date.'})
    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)
    return queryset


def _parse_filter_date(value, field):
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError({field: 'Ngày phải theo định dạng YYYY-MM-DD.'})
    return parsed


class AdminReservationListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self, request):
        queryset = BookReservation.objects.select_related(
            'book__book_edition__book_work',
            'requester',
            'owner',
        ).prefetch_related(
            'book__sale_listings',
            'book__lend_listings',
        ).annotate(
            _is_borrow=Exists(
                LendListing.objects.filter(
                    book_id=OuterRef('book_id'),
                    status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
                ),
            ),
        ).order_by('-created_at', '-id')
        return _apply_admin_filters(queryset, request)

    @staticmethod
    def payload(reservation):
        work = reservation.book.book_edition.book_work
        is_borrow = getattr(reservation, '_is_borrow', False)
        if is_borrow:
            listings = reservation.book.lend_listings.all()
            valid_statuses = ('ACTIVE', 'RESERVED', 'ON_LOAN')
        else:
            listings = reservation.book.sale_listings.all()
            valid_statuses = ('ACTIVE', 'RESERVED', 'SOLD')
        listing = next(
            (item for item in listings if item.status in valid_statuses),
            None,
        )
        return {
            'id': reservation.id,
            'status': reservation.status,
            'created_at': reservation.created_at,
            'updated_at': reservation.updated_at,
            'expires_at': reservation.expires_at,
            'requester': {
                'id': reservation.requester_id,
                'name': reservation.requester.full_name,
                'email': reservation.requester.email,
            },
            'owner': {
                'id': reservation.owner_id,
                'name': reservation.owner.full_name,
                'email': reservation.owner.email,
            },
            'book': {
                'id': reservation.book_id,
                'title': listing.title if listing else work.title,
                'status': reservation.book.status,
                'book_work_id': work.id,
            },
            'listing': (
                {
                    'id': listing.id,
                    'type': 'BORROW' if is_borrow else 'SALE',
                    'title': listing.title,
                    'status': listing.status,
                }
                if listing else None
            ),
        }

    def get(self, request):
        queryset = self.get_queryset(request)
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([self.payload(item) for item in page])


class AdminReservationDetailView(AdminReservationListView):
    def get(self, request, reservation_id):
        reservation = get_object_or_404(
            self.get_queryset(request),
            pk=reservation_id,
        )
        return Response(self.payload(reservation))


class AdminBorrowOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self, request):
        queryset = BorrowOrder.objects.select_related(
            'order',
            'lend_listing',
            'lend_listing__book',
            'lender',
            'borrower',
        ).prefetch_related(
            Prefetch(
                'lend_listing__book__images',
                queryset=BookImage.objects.filter(is_primary=True).order_by('sort_order', 'id'),
                to_attr='primary_images',
            ),
            Prefetch(
                'order__shipments',
                queryset=Shipment.objects.prefetch_related(
                    Prefetch(
                        'tracking_events',
                        queryset=ShipmentTracking.objects.order_by(
                            'occurred_at',
                            'id',
                        ),
                    ),
                ).order_by('id'),
                to_attr='borrow_shipments',
            ),
        ).order_by('-created_at', '-id')
        return _apply_admin_filters(queryset, request, borrow=True)

    @staticmethod
    def payload(borrow):
        payload = BorrowOrderListView._borrow_payload(borrow)
        payload.update({
            'borrower': {
                'id': borrow.borrower_id,
                'name': borrow.borrower.full_name,
                'email': borrow.borrower.email,
            },
            'owner': {
                'id': borrow.lender_id,
                'name': borrow.lender.full_name,
                'email': borrow.lender.email,
            },
            'book_id': borrow.lend_listing.book_id,
            'listing': {
                'id': borrow.lend_listing_id,
                'title': borrow.lend_listing.title,
                'status': borrow.lend_listing.status,
            },
            'shipments': [
                {
                    'id': shipment.id,
                    'direction': (
                        'BORROWER_TO_OWNER'
                        if borrow.return_tracking_code
                        and shipment.tracking_code == borrow.return_tracking_code
                        else 'OWNER_TO_BORROWER'
                    ),
                    'status': shipment.status,
                    'carrier': shipment.carrier,
                    'tracking_code': shipment.tracking_code,
                    'created_at': shipment.created_at,
                }
                for shipment in getattr(borrow.order, 'borrow_shipments', ())
            ],
        })
        return payload

    def get(self, request):
        queryset = self.get_queryset(request)
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([self.payload(item) for item in page])


class AdminBorrowOrderDetailView(AdminBorrowOrderListView):
    def get(self, request, borrow_order_id):
        borrow = get_object_or_404(
            self.get_queryset(request),
            pk=borrow_order_id,
        )
        return Response(self.payload(borrow))


ORDER_STATUSES = tuple(value for value, _label in Order.STATUS_CHOICES)


class AdminOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self, request):
        orders = Order.objects.select_related(
            'buyer',
            'seller',
            'borrow_order__lender',
            'borrow_order__borrower',
            'borrow_order__lend_listing',
        ).prefetch_related(
            Prefetch(
                'sale_items',
                queryset=SaleOrderItem.objects.select_related(
                    'book',
                    'sale_listing',
                    'seller',
                ).order_by('id'),
            ),
            Prefetch(
                'payments',
                queryset=Payment.objects.order_by('created_at', 'id'),
            ),
            Prefetch(
                'shipments',
                queryset=Shipment.objects.prefetch_related(
                    Prefetch(
                        'tracking_events',
                        queryset=ShipmentTracking.objects.order_by(
                            'occurred_at',
                            'id',
                        ),
                    ),
                ).order_by('created_at', 'id'),
            ),
        ).order_by('-created_at', '-id')

        params = request.query_params
        status_value = params.get('status', '').strip().upper()
        if status_value:
            if status_value not in ORDER_STATUSES:
                raise ValidationError({'status': 'Order status không hợp lệ.'})
            orders = orders.filter(status=status_value)
        order_type = params.get('type', '').strip().upper()
        if order_type:
            if order_type not in ('SALE', 'BORROW'):
                raise ValidationError({'type': 'Order type không hợp lệ.'})
            orders = orders.filter(order_type=order_type)
        for key, field in (('buyer', 'buyer_id'), ('seller', 'seller_id')):
            raw_id = params.get(key)
            if raw_id:
                try:
                    user_id = int(raw_id)
                    if user_id < 1:
                        raise ValueError
                except (TypeError, ValueError) as exc:
                    raise ValidationError({
                        key: 'User ID phải là số nguyên dương.',
                    }) from exc
                orders = orders.filter(**{field: user_id})
        search = params.get('search', '').strip()
        if search:
            orders = orders.filter(
                Q(order_code__icontains=search)
                | Q(buyer__full_name__icontains=search)
                | Q(seller__full_name__icontains=search),
            )
        return orders

    @staticmethod
    def payload(order):
        borrow = getattr(order, 'borrow_order', None)
        buyer = order.buyer
        seller = order.seller or (borrow.lender if borrow else None)
        return {
            'id': order.id,
            'order_code': order.order_code,
            'order_type': order.order_type,
            'status': order.status,
            'buyer': {
                'id': buyer.id,
                'name': buyer.full_name,
                'email': buyer.email,
            },
            'seller': (
                {
                    'id': seller.id,
                    'name': seller.full_name,
                    'email': seller.email,
                }
                if seller else None
            ),
            'amount': str(order.total_amount),
            'currency': order.currency,
            'created_at': order.created_at,
            'updated_at': order.updated_at,
            'completed_at': order.completed_at,
            'payment_status': ', '.join(
                payment.status for payment in order.payments.all()
            ) or None,
            'payments': [
                {
                    'id': payment.id,
                    'status': payment.status,
                    'amount': str(payment.amount),
                    'payment_method': payment.payment_method,
                    'platform_fee': str(payment.platform_fee),
                    'seller_amount': str(payment.seller_amount),
                    'reference': payment.provider_transaction_code,
                    'provider': payment.provider,
                    'paid_at': payment.paid_at,
                }
                for payment in order.payments.all()
            ],
            'items': [
                {
                    'title': item.title_snapshot,
                    'book_id': item.book_id,
                    'listing_id': item.sale_listing_id,
                    'seller': item.seller.full_name,
                    'amount': str(item.subtotal),
                }
                for item in order.sale_items.all()
            ],
            'shipments': [
                {
                    'id': shipment.id,
                    'tracking_number': shipment.tracking_code,
                    'carrier': shipment.carrier,
                    'status': shipment.status,
                    'history': [
                        {
                            'id': event.id,
                            'status': event.status,
                            'source': event.source or 'LEGACY',
                            'changed_by_id': event.changed_by_id,
                            'location': event.location,
                            'note': event.description,
                            'occurred_at': event.occurred_at,
                        }
                        for event in shipment.tracking_events.all()
                    ],
                }
                for shipment in order.shipments.all()
            ],
        }

    def get(self, request):
        queryset = self.get_queryset(request)
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            self.payload(order) for order in page
        ])


class AdminOrderDetailView(AdminOrderListView):
    def get(self, request, order_id):
        order = get_object_or_404(self.get_queryset(request), pk=order_id)
        return Response(self.payload(order))


class AdminPaymentListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self, request):
        payments = Payment.objects.select_related(
            'order',
            'order__buyer',
            'order__seller',
            'order__borrow_order__lender',
            'payer',
        ).prefetch_related('refunds').order_by('-created_at', '-id')
        params = request.query_params
        method = params.get('method', '').strip().upper()
        if method:
            if method not in ('FAKE', 'TEST', 'COD', 'BANK_TRANSFER'):
                raise ValidationError({'method': 'Payment method không hợp lệ.'})
            payments = payments.filter(payment_method=method)
        payment_status = params.get('status', '').strip().upper()
        if payment_status:
            if payment_status == 'PENDING_VERIFICATION':
                payment_status = 'PROCESSING'
            if payment_status not in (
                'PENDING', 'PROCESSING', 'PAID', 'FAILED', 'REFUNDED',
                'REVERSED', 'CANCELLED',
            ):
                raise ValidationError({'status': 'Payment status không hợp lệ.'})
            payments = payments.filter(status=payment_status)
        order_type = params.get('type', '').strip().upper()
        if order_type:
            if order_type not in ('SALE', 'BORROW'):
                raise ValidationError({'type': 'Order type không hợp lệ.'})
            payments = payments.filter(order__order_type=order_type)
        search = params.get('search', '').strip()
        if search:
            payments = payments.filter(
                Q(provider_transaction_code__icontains=search)
                | Q(order__order_code__icontains=search)
                | Q(order__buyer__full_name__icontains=search)
                | Q(order__seller__full_name__icontains=search)
            )
        return payments

    @staticmethod
    def payload(payment):
        order = payment.order
        borrow = getattr(order, 'borrow_order', None)
        seller = order.seller or (borrow.lender if borrow else None)
        pricing = order.pricing_snapshot or {}
        refunds = list(payment.refunds.order_by('created_at', 'id'))
        return {
            'id': payment.id,
            'order_id': order.id,
            'order_code': order.order_code,
            'order_type': order.order_type,
            'order_status': order.status,
            'customer': {
                'id': order.buyer_id,
                'name': order.buyer.full_name,
                'email': order.buyer.email,
            },
            'seller': (
                {
                    'id': seller.id,
                    'name': seller.full_name,
                    'email': seller.email,
                }
                if seller else None
            ),
            'payment_method': payment.payment_method,
            'provider': payment.provider,
            'status': payment.status,
            'reference': payment.provider_transaction_code,
            'subtotal': str(order.subtotal),
            'platform_fee_rate': str(payment.platform_fee_rate),
            'platform_fee': str(payment.platform_fee),
            'customer_total': str(payment.amount),
            'seller_earnings': str(payment.seller_amount),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'created_at': payment.created_at,
            'updated_at': payment.updated_at,
            'paid_at': payment.paid_at,
            'pricing_snapshot': pricing,
            'refunds': [
                {
                    'id': refund.id,
                    'amount': str(refund.amount),
                    'status': refund.status,
                    'reference': refund.provider_refund_reference,
                    'created_at': refund.created_at,
                    'completed_at': refund.completed_at,
                }
                for refund in refunds
            ],
        }

    def get(self, request):
        paginator = BookPagination()
        page = paginator.paginate_queryset(
            self.get_queryset(request),
            request,
            view=self,
        )
        return paginator.get_paginated_response([
            self.payload(payment) for payment in page
        ])


class AdminPaymentDetailView(AdminPaymentListView):
    def get(self, request, payment_id):
        payment = get_object_or_404(
            self.get_queryset(request),
            pk=payment_id,
        )
        return Response(self.payload(payment))


class AdminBankTransferReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=('PAID', 'FAILED'))


class AdminBankTransferReviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, payment_id):
        serializer = AdminBankTransferReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_object_or_404(
            Payment.objects.select_for_update().select_related('order'),
            pk=payment_id,
        )
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        if payment.payment_method != 'BANK_TRANSFER':
            raise ValidationError('Chỉ Bank Transfer cần Admin xác minh.')
        if payment.status != 'PROCESSING' or order.status != 'PENDING_PAYMENT':
            raise ValidationError('Payment không còn chờ xác minh.')

        now = timezone.now()
        target_status = serializer.validated_data['status']
        if target_status == 'PAID':
            paid_exists = Payment.objects.select_for_update().filter(
                order=order,
                status__in=('PAID', 'REFUNDED'),
            ).exclude(pk=payment.pk).exists()
            if paid_exists:
                raise ValidationError('Order đã có Payment thành công.')
            for item in SaleOrderItem.objects.select_for_update().filter(
                order=order,
            ).select_related('sale_listing', 'book'):
                if item.sale_listing.status != 'ACTIVE' or item.book.status != 'AVAILABLE':
                    raise ValidationError(
                        'Sản phẩm không còn khả dụng để xác nhận chuyển khoản.',
                    )
                item.sale_listing.status = 'SOLD'
                item.sale_listing.updated_at = now
                item.sale_listing.save(update_fields=['status', 'updated_at'])
                item.book.status = 'SOLD'
                item.book.updated_at = now
                item.book.save(update_fields=['status', 'updated_at'])
            previous_order_status = order.status
            order.status = 'CONFIRMED'
            order.updated_at = now
            order.save(update_fields=['status', 'updated_at'])
            payment.paid_at = now
            notify_order_status_changed(order, previous_order_status)
        else:
            order.status = 'CANCELLED'
            order.updated_at = now
            order.save(update_fields=['status', 'updated_at'])
        payment.status = target_status
        payment.updated_at = now
        payment.save(update_fields=['status', 'paid_at', 'updated_at'])
        return Response(AdminPaymentListView.payload(payment))


SHIPMENT_TYPES = ('SALE', 'BORROW', 'BORROW_RETURN')


class AdminShipmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SHIPMENT_STATUSES)
    note = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    location = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AdminShipmentListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self, request):
        shipments = Shipment.objects.select_related(
            'order',
            'order__buyer',
            'order__seller',
            'order__borrow_order',
            'order__borrow_order__lender',
            'order__borrow_order__borrower',
        ).prefetch_related(
            Prefetch(
                'tracking_events',
                queryset=ShipmentTracking.objects.order_by(
                    'occurred_at',
                    'id',
                ),
            ),
        ).annotate(
            _is_return_shipment=Exists(
                BorrowOrder.objects.filter(
                    order_id=OuterRef('order_id'),
                    return_tracking_code=OuterRef('tracking_code'),
                ).exclude(return_tracking_code__isnull=True).exclude(
                    return_tracking_code='',
                ),
            ),
        ).order_by('-created_at', '-id')

        status_value = request.query_params.get('status', '').strip().upper()
        if status_value:
            if status_value not in SHIPMENT_STATUSES:
                raise ValidationError({'status': 'Trạng thái Shipment không hợp lệ.'})
            shipments = shipments.filter(status=status_value)

        shipment_type = request.query_params.get('type', '').strip().upper()
        if shipment_type:
            if shipment_type not in SHIPMENT_TYPES:
                raise ValidationError({'type': 'Loại Shipment không hợp lệ.'})
            if shipment_type == 'SALE':
                shipments = shipments.filter(order__order_type='SALE')
            elif shipment_type == 'BORROW':
                shipments = shipments.filter(
                    order__order_type='BORROW',
                    _is_return_shipment=False,
                )
            else:
                shipments = shipments.filter(
                    order__order_type='BORROW',
                    _is_return_shipment=True,
                )

        search = request.query_params.get(
            'search',
            request.query_params.get('tracking', ''),
        ).strip()
        if search:
            shipments = shipments.filter(tracking_code__icontains=search)
        return shipments

    @staticmethod
    def payload(shipment):
        order = shipment.order
        borrow = getattr(order, 'borrow_order', None)
        return_shipment = bool(
            borrow and is_return_shipment(shipment, borrow)
        )
        if borrow:
            shipment_type = 'BORROW_RETURN' if return_shipment else 'BORROW'
            sender = borrow.borrower if return_shipment else borrow.lender
            receiver = borrow.lender if return_shipment else borrow.borrower
            direction = (
                'BORROWER_TO_OWNER'
                if return_shipment
                else 'OWNER_TO_BORROWER'
            )
            borrow_reference = {
                'id': borrow.id,
                'status': borrow.status,
            }
        else:
            shipment_type = 'SALE'
            sender = order.seller
            receiver = order.buyer
            direction = 'SELLER_TO_BUYER'
            borrow_reference = None

        history = []
        for event in shipment.tracking_events.all():
            history.append({
                'id': event.id,
                'status': event.status,
                'location': event.location,
                'note': event.description,
                'source': event.source or 'LEGACY',
                'changed_by_id': event.changed_by_id,
                'occurred_at': event.occurred_at,
            })

        def person(user):
            return (
                {
                    'id': user.id,
                    'name': user.full_name,
                    'email': user.email,
                }
                if user else None
            )

        return {
            'id': shipment.id,
            'tracking_number': shipment.tracking_code,
            'tracking_code': shipment.tracking_code,
            'carrier': shipment.carrier,
            'type': shipment_type,
            'direction': direction,
            'order': {
                'id': order.id,
                'code': order.order_code,
                'type': order.order_type,
                'status': order.status,
            },
            'borrow': borrow_reference,
            'sender': person(sender),
            'receiver': person(receiver),
            'status': shipment.status,
            'shipped_at': shipment.shipped_at,
            'delivered_at': shipment.delivered_at,
            'created_at': shipment.created_at,
            'updated_at': shipment.updated_at,
            'status_history': history,
            'allowed_next_statuses': sorted(
                SHIPMENT_TRANSITIONS.get(shipment.status, set()),
            ),
        }

    def get(self, request):
        shipments = self.get_queryset(request)
        paginator = BookPagination()
        page = paginator.paginate_queryset(shipments, request, view=self)
        return paginator.get_paginated_response([
            self.payload(shipment)
            for shipment in page
        ])


class AdminShipmentDetailView(AdminShipmentListView):
    def get(self, request, shipment_id):
        shipment = get_object_or_404(
            self.get_queryset(request),
            pk=shipment_id,
        )
        return Response(self.payload(shipment))


class AdminShipmentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, shipment_id):
        serializer = AdminShipmentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipment = get_object_or_404(
            Shipment.objects.select_for_update().select_related('order'),
            pk=shipment_id,
        )
        borrow = BorrowOrder.objects.select_for_update().filter(
            order_id=shipment.order_id,
        ).first()
        old_status = shipment.status
        event, old_status = update_shipment_status(
            shipment,
            status=serializer.validated_data['status'],
            source='ADMIN',
            changed_by=request.user,
            borrow=borrow,
            location=serializer.validated_data.get('location'),
            description=serializer.validated_data.get('note'),
            event_model=ShipmentTracking,
        )
        return Response({
            'id': shipment.id,
            'tracking_number': shipment.tracking_code,
            'status': shipment.status,
            'old_status': old_status,
            'source': 'ADMIN',
            'status_event_id': event.id,
        })
