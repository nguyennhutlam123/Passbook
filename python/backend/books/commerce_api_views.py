import hashlib
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import UserAddress
from .models import (
    Book,
    BookImage,
    BookIdentifier,
    BookRequest,
    BookReservation,
    BorrowTerms,
    BorrowOrder,
    Cart,
    CartItem,
    BookWorkSubject,
    CheckoutGroup,
    LendListing,
    Order,
    Payment,
    Refund,
    Review,
    Return,
    SaleListing,
    SaleOrderItem,
    Shipment,
    ShipmentTracking,
)
from .services import (
    FakePaymentProvider,
    PaymentProviderUnavailable,
    calculate_payment_split,
    fake_payments_enabled,
    get_payment_provider,
    transition_borrow_order,
    transition_fake_payment,
    transition_fake_refund,
    transition_reservation,
)
from .pagination import BookPagination


def _query_integer(params, name):
    value = params.get(name)
    if value in (None, ''):
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise serializers.ValidationError({name: f'{name} phải là số nguyên.'}) from exc
    if parsed < 1:
        raise serializers.ValidationError({name: f'{name} phải lớn hơn 0.'})
    return parsed


def _query_decimal(params, name):
    value = params.get(name)
    if value in (None, ''):
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise serializers.ValidationError({name: f'{name} không hợp lệ.'}) from exc
    if not parsed.is_finite() or parsed < 0:
        raise serializers.ValidationError({name: f'{name} không hợp lệ.'})
    return parsed


def active_cart_for(user):
    now = timezone.now()
    cart = Cart.objects.filter(user=user, status='ACTIVE').first()
    if cart is None:
        try:
            cart = Cart.objects.create(
                user=user,
                status='ACTIVE',
                created_at=now,
                updated_at=now,
            )
        except IntegrityError:
            cart = Cart.objects.get(user=user, status='ACTIVE')
    return cart


def cart_payload(cart):
    items = list(
        cart.items.select_related(
            'sale_listing__book__book_edition__book_work',
            'sale_listing__seller__university',
            'lend_listing__book__book_edition__book_work',
            'lend_listing__lender__university',
        ).prefetch_related(
            Prefetch(
                'sale_listing__book__images',
                queryset=BookImage.objects.order_by('-is_primary', 'sort_order', 'id'),
                to_attr='cart_images',
            ),
            Prefetch(
                'lend_listing__book__images',
                queryset=BookImage.objects.order_by('-is_primary', 'sort_order', 'id'),
                to_attr='cart_images',
            ),
        ).order_by('created_at', 'id')
    )
    payload_items = []
    total = Decimal('0')
    for item in items:
        listing = item.sale_listing if item.sale_listing_id else item.lend_listing
        book = listing.book
        seller = listing.seller if item.sale_listing_id else listing.lender
        unit_price = listing.price if item.sale_listing_id else listing.rental_fee
        if item.lend_listing_id:
            unit_price += listing.deposit_amount or Decimal('0')
        total += unit_price
        images = getattr(book, 'cart_images', [])
        payload_items.append({
            'id': item.id,
            'listing_type': 'SALE' if item.sale_listing_id else 'BORROW',
            'listing_id': item.sale_listing_id or item.lend_listing_id,
            'book_id': book.id,
            'title': listing.title,
            'unit_price': str(unit_price),
            'currency': listing.currency,
            'condition_status': book.condition_label,
            'seller': {
                'id': seller.id,
                'name': seller.full_name,
                'university': seller.university.name if seller.university_id else None,
            },
            'primary_image': (
                {'id': images[0].id, 'image_url': images[0].image_url}
                if images else None
            ),
            'quantity': 1,
            'subtotal': str(unit_price),
            'listing_status': listing.status,
            'created_at': item.created_at,
        })
    return {
        'id': cart.id,
        'status': cart.status,
        'items': payload_items,
        'subtotal': str(total),
        'shipping_total': '0',
        'total_amount': str(total),
        'currency': 'VND',
    }


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(cart_payload(active_cart_for(request.user)))


class CartItemListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartItemInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        listing_type = data['listing_type']
        listing_id = data['listing_id']
        if listing_type == 'SALE':
            listing = get_object_or_404(
                SaleListing.objects.select_related('book').filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
                ),
                pk=listing_id,
                status='ACTIVE',
                book__status='AVAILABLE',
            )
            if listing.seller_id == request.user.id:
                raise serializers.ValidationError('Không thể mua sách do chính bạn đăng bán.')
            sale_listing = listing
            lend_listing = None
            price = listing.price
        else:
            raise serializers.ValidationError({
                'listing_type': 'Tin cho mượn phải được đăng ký qua yêu cầu mượn, không thêm vào giỏ.',
            })

        cart = active_cart_for(request.user)
        now = timezone.now()
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            sale_listing=sale_listing,
            lend_listing=lend_listing,
            defaults={
                'unit_price': price,
                'currency': 'VND',
                'created_at': now,
                'updated_at': now,
            },
        )
        if not created:
            item.unit_price = price
            item.updated_at = now
            item.save(update_fields=['unit_price', 'updated_at'])
        return Response(
            cart_payload(cart),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        cart = Cart.objects.filter(
            user=request.user,
            status='ACTIVE',
        ).first()
        if cart is not None:
            cart.items.all().delete()
            cart.updated_at = timezone.now()
            cart.save(update_fields=['updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        item = get_object_or_404(
            CartItem.objects.select_related('cart'),
            pk=item_id,
            cart__user=request.user,
            cart__status='ACTIVE',
        )
        serializer = CartItemInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['listing_type'] == 'SALE':
            listing = get_object_or_404(
                SaleListing.objects.filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
                ),
                pk=data['listing_id'],
                status='ACTIVE',
                book__status='AVAILABLE',
            )
            if listing.seller_id == request.user.id:
                raise serializers.ValidationError('Không thể mua sách do chính bạn đăng bán.')
            item.sale_listing = listing
            item.lend_listing = None
            item.unit_price = listing.price
        else:
            raise serializers.ValidationError({
                'listing_type': 'Tin cho mượn không thuộc giỏ hàng.',
            })
        item.updated_at = timezone.now()
        item.save(update_fields=[
            'sale_listing', 'lend_listing', 'unit_price', 'updated_at',
        ])
        return Response(cart_payload(item.cart))

    def delete(self, request, item_id):
        item = get_object_or_404(
            CartItem.objects.select_related('cart'),
            pk=item_id,
            cart__user=request.user,
            cart__status='ACTIVE',
        )
        cart = item.cart
        item.delete()
        return Response(cart_payload(cart), status=status.HTTP_200_OK)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart_item_id = _query_integer(request.query_params, 'cart_item_id')
        if cart_item_id is None:
            raise serializers.ValidationError({
                'cart_item_id': 'Chọn một sản phẩm trong giỏ hàng để xem báo giá.',
            })
        item = get_object_or_404(
            CartItem.objects.select_related(
                'cart',
                'sale_listing__book',
                'sale_listing__seller',
                'lend_listing__book',
                'lend_listing__lender',
            ),
            pk=cart_item_id,
            cart__user=request.user,
            cart__status='ACTIVE',
        )
        line = self._checkout_line(item, request.user)
        subtotal = line['amount']
        return Response({
            'cart_item_id': item.id,
            'items': [{
                'title': line['listing'].title,
                'unit_price': str(line['unit_price']),
                'quantity': 1,
                'subtotal': str(subtotal),
                'currency': line['listing'].currency,
            }],
            'subtotal': str(subtotal),
            'shipping_total': '0',
            'total_amount': str(subtotal),
            'currency': line['listing'].currency,
        })

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        existing = CheckoutGroup.objects.filter(
            buyer=request.user,
            idempotency_key=data['idempotency_key'],
        ).first()
        if existing is not None:
            return Response(checkout_payload(existing), status=status.HTTP_200_OK)

        cart = Cart.objects.select_for_update().filter(
            user=request.user,
            status='ACTIVE',
        ).first()
        if cart is None:
            existing = CheckoutGroup.objects.filter(
                buyer=request.user,
                idempotency_key=data['idempotency_key'],
            ).first()
            if existing is not None:
                return Response(checkout_payload(existing), status=status.HTTP_200_OK)
            raise serializers.ValidationError(
                {'cart': 'Giỏ hàng không còn hoạt động; hãy tải lại giỏ hàng.'},
            )
        items_query = CartItem.objects.select_for_update().filter(cart=cart)
        if data.get('cart_item_id') is not None:
            items_query = items_query.filter(pk=data['cart_item_id'])
        items = list(
            items_query
            .select_related('sale_listing', 'lend_listing')
            .order_by('id')
        )
        if not items:
            raise serializers.ValidationError({'cart': 'Giỏ hàng đang trống.'})

        shipping_snapshot = self._shipping_snapshot(request.user, data)
        address_serializer = CheckoutAddressInputSerializer(data=shipping_snapshot)
        address_serializer.is_valid(raise_exception=True)
        shipping_snapshot = address_serializer.validated_data
        now = timezone.now()
        sale_groups = defaultdict(list)
        for item in items:
            if item.sale_listing_id:
                listing = SaleListing.objects.select_for_update().select_related(
                    'book', 'seller',
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=now),
                ).filter(
                    pk=item.sale_listing_id,
                    status='ACTIVE',
                    book__status='AVAILABLE',
                ).first()
                if listing is None:
                    raise serializers.ValidationError('Sách này không còn khả dụng.')
                if listing.seller_id == request.user.id:
                    raise serializers.ValidationError('Không thể mua sách do chính bạn đăng bán.')
                sale_groups[listing.seller_id].append((item, listing))
            elif item.lend_listing_id:
                raise serializers.ValidationError(
                    'Tin cho mượn không thể thanh toán qua Cart/Order; hãy tạo yêu cầu mượn.',
                )
            else:
                raise serializers.ValidationError('Cart item không có listing hợp lệ.')

        subtotal = sum(
            (listing.price for group in sale_groups.values() for _, listing in group),
            Decimal('0'),
        )
        if not fake_payments_enabled():
            return Response(
                {'detail': 'Thanh toán giả lập chỉ khả dụng trong local/test.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        payment_provider = get_payment_provider('fake')
        if not isinstance(payment_provider, FakePaymentProvider):
            raise PaymentProviderUnavailable('Fake payment provider không khả dụng.')
        payment_status = {
            'SUCCESS': 'PAID',
            'FAILURE': 'FAILED',
            'CANCEL': 'CANCELLED',
        }[data['payment_outcome']]
        payment_provider.transition('PENDING', payment_status)
        if payment_status != 'PAID':
            message = (
                'Bạn đã hủy thanh toán; đơn hàng chưa được tạo và giỏ hàng vẫn được giữ.'
                if payment_status == 'CANCELLED'
                else 'Thanh toán thất bại; đơn hàng chưa được tạo và giỏ hàng vẫn được giữ.'
            )
            return Response(
                {'detail': message, 'payment_status': payment_status},
                status=status.HTTP_409_CONFLICT if payment_status == 'CANCELLED'
                else status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            fee_rate = Decimal(getattr(settings, 'PASSBOOK_PLATFORM_FEE_RATE', '0'))
        except (InvalidOperation, ValueError) as exc:
            raise serializers.ValidationError('Cấu hình tỷ lệ phí không hợp lệ.') from exc
        with transaction.atomic():
            created_orders = []
            checkout = CheckoutGroup.objects.create(
                checkout_code=f'CHK-{uuid4().hex[:24].upper()}',
                idempotency_key=data['idempotency_key'],
                cart=cart,
                buyer=request.user,
                status='COMPLETED',
                currency='VND',
                subtotal=subtotal,
                shipping_total=Decimal('0'),
                discount_total=Decimal('0'),
                total_amount=subtotal,
                shipping_address_snapshot=shipping_snapshot,
                pricing_snapshot={
                    'subtotal': str(subtotal),
                    'shipping_total': '0',
                    'discount_total': '0',
                    'total_amount': str(subtotal),
                    'currency': 'VND',
                },
                created_at=now,
                updated_at=now,
                completed_at=now,
            )

            for seller_id, listings in sale_groups.items():
                group_total = sum((listing.price for _, listing in listings), Decimal('0'))
                order = Order.objects.create(
                    order_code=f'ORD-{uuid4().hex[:24].upper()}',
                    checkout_group=checkout,
                    buyer=request.user,
                    seller_id=seller_id,
                    order_type='SALE',
                    status='CONFIRMED',
                    currency='VND',
                    subtotal=group_total,
                    shipping_fee=Decimal('0'),
                    discount_amount=Decimal('0'),
                    total_amount=group_total,
                    shipping_address_snapshot=shipping_snapshot,
                    pricing_snapshot={
                        'subtotal': str(group_total),
                        'shipping_fee': '0',
                        'total_amount': str(group_total),
                        'currency': 'VND',
                    },
                    placed_at=now,
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                )
                created_orders.append((order, group_total))
                for _, listing in listings:
                    SaleOrderItem.objects.create(
                        order=order,
                        sale_listing=listing,
                        book=listing.book,
                        seller=listing.seller,
                        title_snapshot=listing.title,
                        condition_snapshot=listing.book.condition_label,
                        unit_price=listing.price,
                        discount_allocated=Decimal('0'),
                        quantity=1,
                        subtotal=listing.price,
                        created_at=now,
                    )
                    listing.status = 'SOLD'
                    listing.updated_at = now
                    listing.save(update_fields=['status', 'updated_at'])
                    listing.book.status = 'SOLD'
                    listing.book.updated_at = now
                    listing.book.save(update_fields=['status', 'updated_at'])

            for order, amount in created_orders:
                split = calculate_payment_split(amount, fee_rate)
                payment_idempotency_key = hashlib.sha256(
                    f"{data['idempotency_key']}:{order.id}".encode(),
                ).hexdigest()
                provider_reference = payment_provider.create_payment_intent(
                    payment_idempotency_key,
                    split['amount'],
                    order.currency,
                )
                Payment.objects.create(
                    checkout_group=checkout,
                    order=order,
                    payer=request.user,
                    provider='fake',
                    payment_method=data['payment_method'],
                    provider_transaction_code=provider_reference,
                    payment_purpose='CHECKOUT',
                    amount=split['amount'],
                    platform_fee_rate=split['platform_fee_rate'],
                    platform_fee=split['platform_fee'],
                    seller_amount=split['seller_amount'],
                    currency=order.currency,
                    status='PAID',
                    idempotency_key=payment_idempotency_key,
                    paid_at=now,
                    created_at=now,
                    updated_at=now,
                )

            CartItem.objects.filter(
                cart=cart,
                pk__in=[item.id for item in items],
            ).delete()
            if not cart.items.exists():
                cart.status = 'CHECKED_OUT'
            cart.updated_at = now
            cart.save(update_fields=['status', 'updated_at'])
        return Response(checkout_payload(checkout), status=status.HTTP_201_CREATED)

    @staticmethod
    def _checkout_line(item, user):
        now = timezone.now()
        if item.sale_listing_id:
            listing = SaleListing.objects.select_related('book').filter(
                pk=item.sale_listing_id,
                status='ACTIVE',
                book__status='AVAILABLE',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            ).first()
            if listing is None:
                raise serializers.ValidationError('Sách này không còn khả dụng.')
            if listing.seller_id == user.id:
                raise serializers.ValidationError('Không thể mua sách do chính bạn đăng bán.')
            return {'listing': listing, 'unit_price': listing.price, 'amount': listing.price}

        raise serializers.ValidationError(
            'Tin cho mượn phải được đăng ký qua yêu cầu mượn, không qua Cart/Checkout.',
        )

    @staticmethod
    def _shipping_snapshot(user, data):
        address_id = data.get('user_address_id')
        if address_id is not None:
            address = get_object_or_404(UserAddress, pk=address_id, user=user)
            return {
                'recipient_name': address.recipient_name,
                'phone': address.phone,
                'address_line': address.address_line,
                'ward': address.ward or '',
                'district': address.district or '',
                'city': address.city,
                'postal_code': address.postal_code or '',
            }
        return data.get('shipping_address_snapshot', {})


class CheckoutInputSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=128, allow_blank=False, trim_whitespace=True)
    cart_item_id = serializers.IntegerField(required=False, min_value=1)
    user_address_id = serializers.IntegerField(required=False, min_value=1)
    shipping_address_snapshot = serializers.DictField(required=False, default=dict)
    payment_outcome = serializers.ChoiceField(
        choices=('SUCCESS', 'FAILURE', 'CANCEL'),
        default='SUCCESS',
    )
    payment_method = serializers.ChoiceField(choices=('TEST',), default='TEST')


class CheckoutAddressInputSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    phone = serializers.CharField(max_length=30, allow_blank=False, trim_whitespace=True)
    address_line = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    city = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    ward = serializers.CharField(max_length=255, allow_blank=True, required=False)
    district = serializers.CharField(max_length=255, allow_blank=True, required=False)
    postal_code = serializers.CharField(max_length=30, allow_blank=True, required=False)


class CartItemInputSerializer(serializers.Serializer):
    listing_type = serializers.ChoiceField(choices=('SALE',))
    listing_id = serializers.IntegerField(min_value=1)


class ReservationInputSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField()

    def validate_expires_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Thời hạn đặt sách phải ở tương lai.')
        return value


class LendListingListCreateView(APIView):
    def get_permissions(self):
        permission = IsAuthenticated if self.request.method == 'POST' else AllowAny
        return [permission()]

    def get(self, request):
        queryset = LendListing.objects.filter(
            status='ACTIVE',
            book__status='AVAILABLE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        ).select_related(
            'book__book_edition__book_work',
            'book__book_edition__book_work__category',
            'book__book_edition__language',
            'lender__university',
        )
        subject_links = BookWorkSubject.objects.filter(
            is_primary=True,
        ).select_related('subject')
        queryset = queryset.prefetch_related(
            Prefetch(
                'book__images',
                queryset=BookImage.objects.filter(is_primary=True).order_by('sort_order', 'id'),
                to_attr='catalog_images',
            ),
            Prefetch(
                'book__book_edition__book_work__subject_links',
                queryset=subject_links,
                to_attr='primary_subject_links',
            ),
            Prefetch(
                'borrow_terms',
                queryset=BorrowTerms.objects.only(
                    'id',
                    'lend_listing_id',
                    'max_days',
                    'late_fee_per_day',
                    'deposit_required',
                    'shipping_paid_by',
                    'return_method',
                    'notes',
                ),
                to_attr='listing_terms',
            ),
        )
        active_intents = BookRequest.objects.filter(
            book_work_id=OuterRef('book__book_edition__book_work_id'),
            status='OPEN',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        )
        queryset = queryset.annotate(
            buying_intent_count=Coalesce(
                Subquery(
                    active_intents.filter(request_type='BUY')
                    .order_by()
                    .values('book_work_id')
                    .annotate(total=Count('user_id', distinct=True))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            selling_intent_count=Coalesce(
                Subquery(
                    active_intents.filter(request_type='SELL_INTENT')
                    .order_by()
                    .values('book_work_id')
                    .annotate(total=Count('user_id', distinct=True))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
        )
        params = request.query_params
        search = (params.get('search') or '').strip()
        if search:
            identifier_match = BookIdentifier.objects.filter(
                book_edition_id=OuterRef('book__book_edition_id'),
                identifier_value__icontains=search,
            )
            subject_match = BookWorkSubject.objects.filter(
                book_work_id=OuterRef('book__book_edition__book_work_id'),
            ).filter(
                Q(subject__name__icontains=search)
                | Q(subject__code__icontains=search),
            )
            queryset = queryset.annotate(
                _subject_match=Exists(subject_match),
                _identifier_match=Exists(identifier_match),
            ).filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(book__book_edition__book_work__title__icontains=search)
                | Q(book__book_edition__book_work__description__icontains=search)
                | Q(book__book_edition__book_work__author_name__icontains=search)
                | Q(book__book_edition__edition_name__icontains=search)
                | Q(book__book_edition__publisher_name__icontains=search)
                | Q(book__book_edition__book_work__category__name__icontains=search)
                | Q(lender__university__name__icontains=search)
                | Q(lender__faculty__name__icontains=search)
                | Q(lender__major__name__icontains=search)
                | Q(_subject_match=True)
                | Q(_identifier_match=True),
            )
        subject_id = _query_integer(params, 'subject_id')
        if subject_id is not None:
            queryset = queryset.filter(Exists(
                BookWorkSubject.objects.filter(
                    book_work_id=OuterRef('book__book_edition__book_work_id'),
                    subject_id=subject_id,
                ),
            ))
        subject_code = (params.get('subject_code') or '').strip()
        if subject_code:
            queryset = queryset.filter(Exists(
                BookWorkSubject.objects.filter(
                    book_work_id=OuterRef('book__book_edition__book_work_id'),
                    subject__code__icontains=subject_code,
                ),
            ))
        author = (params.get('author') or '').strip()
        if author:
            queryset = queryset.filter(
                book__book_edition__book_work__author_name__icontains=author,
            )
        isbn = (params.get('isbn') or '').strip()
        if isbn:
            queryset = queryset.filter(Exists(
                BookIdentifier.objects.filter(
                    book_edition_id=OuterRef('book__book_edition_id'),
                    identifier_type__icontains='ISBN',
                    identifier_value__icontains=isbn,
                ),
            ))
        category_id = _query_integer(params, 'category_id')
        if category_id is not None:
            queryset = queryset.filter(
                book__book_edition__book_work__category_id=category_id,
            )
        publication_year = _query_integer(params, 'publication_year')
        if publication_year is not None:
            queryset = queryset.filter(
                book__book_edition__publication_year=publication_year,
            )
        language_id = _query_integer(params, 'language_id')
        if language_id is not None:
            queryset = queryset.filter(book__book_edition__language_id=language_id)
        edition = (params.get('edition') or '').strip()
        if edition:
            queryset = queryset.filter(
                book__book_edition__edition_name__icontains=edition,
            )
        university_id = _query_integer(params, 'university_id')
        if university_id is not None:
            queryset = queryset.filter(lender__university_id=university_id)
        faculty_id = _query_integer(params, 'faculty_id')
        if faculty_id is not None:
            queryset = queryset.filter(lender__faculty_id=faculty_id)
        major_id = _query_integer(params, 'major_id')
        if major_id is not None:
            queryset = queryset.filter(lender__major_id=major_id)
        for parameter, relation in (
            ('university', 'lender__university__name'),
            ('faculty', 'lender__faculty__name'),
            ('major', 'lender__major__name'),
        ):
            value = (params.get(parameter) or '').strip()
            if value:
                queryset = queryset.filter(**{f'{relation}__icontains': value})
        subject = (params.get('subject') or '').strip()
        if subject:
            queryset = queryset.filter(Exists(
                BookWorkSubject.objects.filter(
                    book_work_id=OuterRef('book__book_edition__book_work_id'),
                ).filter(
                    Q(subject__name__icontains=subject)
                    | Q(subject__code__icontains=subject),
                ),
            ))
        condition = params.get('condition_status')
        if condition:
            if condition not in {value for value, _ in Book.CONDITION_CHOICES}:
                raise serializers.ValidationError({
                    'condition_status': 'Tình trạng không hợp lệ.',
                })
            queryset = queryset.filter(book__condition_label__iexact=condition)
        minimum = _query_decimal(params, 'min_price')
        maximum = _query_decimal(params, 'max_price')
        if minimum is not None:
            queryset = queryset.filter(rental_fee__gte=minimum)
        if maximum is not None:
            queryset = queryset.filter(rental_fee__lte=maximum)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError({
                'price': 'min_price không được lớn hơn max_price.',
            })
        sort_options = {
            'newest': ('-created_at', '-id'),
            'oldest': ('created_at', 'id'),
            'price_asc': ('rental_fee', 'id'),
            'price_desc': ('-rental_fee', '-id'),
        }
        sort = params.get('sort', 'newest')
        if sort not in sort_options:
            raise serializers.ValidationError({'sort': 'Giá trị sort không hợp lệ.'})
        queryset = queryset.order_by(*sort_options[sort])
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            lend_listing_payload(listing) for listing in page
        ])

    @transaction.atomic
    def post(self, request):
        if not request.user.is_authenticated:
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated()
        serializer = LendListingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        book = get_object_or_404(
            Book.objects.select_for_update().select_related(
                'book_edition__book_work',
            ),
            pk=data['book_id'],
            owner=request.user,
            status='AVAILABLE',
        )
        if LendListing.objects.filter(
            book=book,
            status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
        ).exists():
            raise serializers.ValidationError('Sách đã có tin cho mượn đang hoạt động.')
        if SaleListing.objects.filter(
            book=book,
            status__in=('PENDING', 'ACTIVE', 'RESERVED', 'SOLD'),
        ).exists():
            raise serializers.ValidationError('Sách đã có tin bán chưa thể cho mượn.')
        now = timezone.now()
        with transaction.atomic():
            listing = LendListing.objects.create(
                book=book,
                lender=request.user,
                title=data.get('title') or book.book_edition.book_work.title,
                description=data.get('description'),
                status='ACTIVE',
                deposit_amount=data.get('deposit_amount'),
                rental_fee=data['rental_fee'],
                published_at=now,
                created_at=now,
                updated_at=now,
            )
            terms = BorrowTerms.objects.create(
                lend_listing=listing,
                max_days=data['max_days'],
                late_fee_per_day=data.get('late_fee_per_day'),
                deposit_required=data.get('deposit_required', False),
                shipping_paid_by=data['shipping_paid_by'],
                return_method=data['return_method'],
                notes=data.get('terms_notes'),
                created_at=now,
                updated_at=now,
            )
            listing.listing_terms = terms
        return Response(lend_listing_payload(listing), status=status.HTTP_201_CREATED)


class LendListingInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    rental_fee = serializers.DecimalField(max_digits=19, decimal_places=4, min_value=0)
    deposit_amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    max_days = serializers.IntegerField(min_value=1)
    late_fee_per_day = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    deposit_required = serializers.BooleanField(required=False, default=False)
    shipping_paid_by = serializers.CharField(max_length=20)
    return_method = serializers.CharField(max_length=30)
    terms_notes = serializers.CharField(required=False, allow_blank=True)


class LendListingDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, listing_id):
        listing = get_object_or_404(
            LendListing.objects.filter(
                status='ACTIVE',
                book__status='AVAILABLE',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            ).select_related(
                'book__book_edition__book_work__category',
                'book__book_edition__language',
                'lender__university',
            ).prefetch_related(
                Prefetch(
                    'book__images',
                    queryset=BookImage.objects.order_by('sort_order', 'id'),
                    to_attr='catalog_images',
                ),
                Prefetch(
                    'book__book_edition__book_work__subject_links',
                    queryset=BookWorkSubject.objects.filter(
                        is_primary=True,
                    ).select_related('subject'),
                    to_attr='primary_subject_links',
                ),
                Prefetch(
                    'borrow_terms',
                    queryset=BorrowTerms.objects.only(
                        'id',
                        'lend_listing_id',
                        'max_days',
                        'late_fee_per_day',
                        'deposit_required',
                        'shipping_paid_by',
                        'return_method',
                        'notes',
                    ),
                    to_attr='listing_terms',
                ),
            ),
            pk=listing_id,
        )
        return Response(lend_listing_payload(listing))


def lend_listing_payload(listing):
    book = listing.book
    edition = book.book_edition
    work = edition.book_work
    subject_links = getattr(work, 'primary_subject_links', ())
    subject = subject_links[0].subject if subject_links else None
    images = getattr(book, 'catalog_images', None)
    if images is None:
        images = list(book.images.order_by('sort_order', 'id'))
    primary_image = next(
        (image for image in images if image.is_primary),
        images[0] if images else None,
    )
    language = edition.language
    condition_label = dict(Book.CONDITION_CHOICES).get(
        book.condition_status,
        book.condition_label,
    )
    terms = getattr(listing, 'listing_terms', None)
    return {
        'id': listing.id,
        'book_id': listing.book_id,
        'lender_id': listing.lender_id,
        'listing_type': 'BORROW',
        'title': listing.title,
        'description': listing.description,
        'status': listing.status,
        'deposit_amount': str(listing.deposit_amount) if listing.deposit_amount is not None else None,
        'rental_fee': str(listing.rental_fee),
        'borrow_terms': (
            {
                'max_days': terms.max_days,
                'late_fee_per_day': (
                    str(terms.late_fee_per_day)
                    if terms.late_fee_per_day is not None else None
                ),
                'deposit_required': terms.deposit_required,
                'shipping_paid_by': terms.shipping_paid_by,
                'return_method': terms.return_method,
                'notes': terms.notes,
            }
            if terms is not None else None
        ),
        'currency': listing.currency,
        'primary_image': primary_image.image_url if primary_image else None,
        'images': [
            {
                'id': image.id,
                'image_url': image.image_url,
                'cloudinary_public_id': image.cloudinary_public_id,
                'is_primary': image.is_primary,
                'sort_order': image.sort_order,
            }
            for image in images
        ],
        'condition_status': book.condition_status,
        'condition_label': condition_label,
        'edition': edition.edition_name,
        'publication_year': edition.publication_year,
        'buying_intent_count': getattr(listing, 'buying_intent_count', 0),
        'selling_intent_count': getattr(listing, 'selling_intent_count', 0),
        'subject': (
            {'id': subject.id, 'name': subject.name, 'code': subject.code}
            if subject else None
        ),
        'category': (
            {'id': work.category_id, 'name': work.category.name}
            if work.category_id else None
        ),
        'seller': {
            'id': listing.lender_id,
            'name': listing.lender.full_name,
            'university': (
                {
                    'id': listing.lender.university_id,
                    'name': listing.lender.university.name,
                }
                if listing.lender.university_id else None
            ),
        },
        'book': {
            'id': book.id,
            'title': listing.title,
            'description': listing.description,
            'price': str(listing.rental_fee),
            'status': 'available',
            'condition_status': book.condition_status,
            'condition_label': condition_label,
            'condition_description': book.condition_description,
            'edition': edition.edition_name,
            'edition_number': edition.edition_number,
            'publication_year': edition.publication_year,
            'author': work.author_name,
            'publisher': edition.publisher_name,
            'book_work_id': work.id,
            'buying_intent_count': getattr(listing, 'buying_intent_count', 0),
            'selling_intent_count': getattr(listing, 'selling_intent_count', 0),
            'language': (
                {'id': language.id, 'name': language.name, 'code': language.code}
                if language else None
            ),
            'subject': (
                {'id': subject.id, 'name': subject.name, 'code': subject.code}
                if subject else None
            ),
            'category': (
                {'id': work.category_id, 'name': work.category.name}
                if work.category_id else None
            ),
            'seller': {
                'id': listing.lender_id,
                'name': listing.lender.full_name,
                'university': (
                    {
                        'id': listing.lender.university_id,
                        'name': listing.lender.university.name,
                    }
                    if listing.lender.university_id else None
                ),
            },
            'images': [
                {
                    'id': image.id,
                    'image_url': image.image_url,
                    'is_primary': image.is_primary,
                }
                for image in images
            ],
        },
        'created_at': listing.created_at,
    }


class BookReservationListCreateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request, book_id=None):
        queryset = BookReservation.objects.filter(
            Q(requester=request.user) | Q(owner=request.user),
        ).select_related('book').annotate(
            _is_borrow=Exists(
                LendListing.objects.filter(
                    book_id=OuterRef('book_id'),
                    status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
                ),
            ),
        ).order_by('-created_at', '-id')
        if book_id is not None:
            queryset = queryset.filter(book_id=book_id)
        now = timezone.now()
        expired = list(queryset.filter(
            expires_at__lte=now,
        ).filter(
            Q(status='PENDING') | Q(status='CONFIRMED', _is_borrow=False),
        ).values_list('id', 'book_id'))
        for reservation_id, expired_book_id in expired:
            with transaction.atomic():
                book = Book.objects.select_for_update().get(pk=expired_book_id)
                reservation = BookReservation.objects.select_for_update().get(
                    pk=reservation_id,
                )
                lend_listing = LendListing.objects.select_for_update().filter(
                    book_id=expired_book_id,
                    status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
                ).first()
                should_expire = reservation.status == 'PENDING' or (
                    reservation.status == 'CONFIRMED'
                    and lend_listing is None
                )
                if (
                    should_expire
                    and reservation.expires_at <= now
                ):
                    reservation.status = 'EXPIRED'
                    reservation.updated_at = now
                    reservation.save(update_fields=['status', 'updated_at'])
                    SaleListing.objects.filter(
                        book_id=expired_book_id,
                        status='RESERVED',
                    ).update(status='ACTIVE', updated_at=now)
                    if lend_listing is not None and lend_listing.status == 'RESERVED':
                        lend_listing.status = 'ACTIVE'
                        lend_listing.updated_at = now
                        lend_listing.save(update_fields=['status', 'updated_at'])
                    if book.status == 'RESERVED':
                        book.status = 'AVAILABLE'
                        book.updated_at = now
                        book.save(update_fields=['status', 'updated_at'])
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            {
                'id': item.id,
                'book_id': item.book_id,
                'requester_id': item.requester_id,
                'owner_id': item.owner_id,
                'listing_type': 'BORROW' if item._is_borrow else 'BUY',
                'status': item.status,
                'created_at': item.created_at,
                'expires_at': item.expires_at,
                'updated_at': item.updated_at,
            }
            for item in page
        ])

    @transaction.atomic
    def post(self, request, book_id):
        serializer = ReservationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        book = get_object_or_404(
            Book.objects.select_for_update(),
            pk=book_id,
        )
        if book.owner_id == request.user.id:
            raise serializers.ValidationError('Không thể đặt sách do chính bạn sở hữu.')
        if BookReservation.objects.filter(
            book=book,
            status__in=('PENDING', 'CONFIRMED'),
        ).exists():
            raise serializers.ValidationError('Sách đã có một yêu cầu đặt còn hiệu lực.')
        if book.status != 'AVAILABLE':
            raise serializers.ValidationError('Sách hiện không khả dụng.')
        listing = LendListing.objects.select_for_update().filter(
            book=book,
            status='ACTIVE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        ).first()
        if listing is None:
            if SaleListing.objects.filter(
                book=book,
                status='ACTIVE',
            ).exists():
                raise serializers.ValidationError(
                    'Tin BUY không thể tạo yêu cầu mượn.',
                )
            raise serializers.ValidationError('Sách hiện không có tin cho mượn khả dụng.')
        if BookReservation.objects.filter(
            book=book,
            status__in=('PENDING', 'CONFIRMED'),
        ).exists():
            raise serializers.ValidationError('Sách đã có một yêu cầu đặt còn hiệu lực.')
        now = timezone.now()
        try:
            with transaction.atomic():
                reservation = BookReservation.objects.create(
                    book=book,
                    requester=request.user,
                    owner_id=book.owner_id,
                    status='PENDING',
                    created_at=now,
                    expires_at=serializer.validated_data['expires_at'],
                    updated_at=now,
                )
                listing.status = 'RESERVED'
                listing.updated_at = now
                listing.save(update_fields=['status', 'updated_at'])
                book.status = 'RESERVED'
                book.updated_at = now
                book.save(update_fields=['status', 'updated_at'])
        except IntegrityError as exc:
            raise serializers.ValidationError(
                'Sách vừa được người khác đặt; hãy tải lại danh sách.',
            ) from exc
        reservation._is_borrow = True
        return Response(reservation_payload(reservation), status=status.HTTP_201_CREATED)


class BookReservationActionView(APIView):
    permission_classes = [IsAuthenticated]
    ACTIONS = {'confirm', 'reject', 'cancel', 'complete'}

    def post(self, request, reservation_id, action):
        if action not in self.ACTIONS:
            raise serializers.ValidationError({'action': 'Thao tác không hợp lệ.'})
        get_object_or_404(BookReservation, pk=reservation_id)
        reservation = transition_reservation(
            reservation_id,
            request.user,
            action,
        )
        return Response(reservation_payload(reservation))


def reservation_payload(reservation):
    is_borrow = getattr(reservation, '_is_borrow', None)
    if is_borrow is None:
        is_borrow = LendListing.objects.filter(
            book_id=reservation.book_id,
            status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
        ).exists()
    return {
        'id': reservation.id,
        'book_id': reservation.book_id,
        'requester_id': reservation.requester_id,
        'owner_id': reservation.owner_id,
        'listing_type': 'BORROW' if is_borrow else 'BUY',
        'status': reservation.status,
        'created_at': reservation.created_at,
        'expires_at': reservation.expires_at,
        'updated_at': reservation.updated_at,
    }


class BorrowReturnInputSerializer(serializers.Serializer):
    return_method = serializers.CharField(max_length=30, required=False, allow_blank=True)
    return_tracking_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    return_notes = serializers.CharField(required=False, allow_blank=True)


class BorrowOrderReturnRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, borrow_order_id):
        borrow = get_object_or_404(BorrowOrder, pk=borrow_order_id)
        serializer = BorrowReturnInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        borrow = transition_borrow_order(
            borrow.id,
            request.user,
            'request_return',
        )
        fields = serializer.validated_data
        for name in ('return_method', 'return_tracking_code', 'return_notes'):
            if name in fields:
                setattr(borrow, name, fields[name])
        borrow.save(update_fields=[
            name for name in ('return_method', 'return_tracking_code', 'return_notes')
            if name in fields
        ] or ['updated_at'])
        return Response({
            'id': borrow.id,
            'status': borrow.status,
            'return_status': borrow.return_status,
            'return_method': borrow.return_method,
            'return_tracking_code': borrow.return_tracking_code,
        })


class ReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, status='COMPLETED')
        if request.user.id not in (order.buyer_id, order.seller_id):
            raise PermissionDenied('Chỉ người mua hoặc người bán mới có thể đánh giá.')
        serializer = ReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if order.order_type == 'SALE':
            listing = order.sale_items.select_related('sale_listing').first()
            if listing is None:
                raise serializers.ValidationError('Đơn hàng không có mặt hàng để đánh giá.')
            target = {'sale_listing': listing.sale_listing, 'lend_listing': None}
        else:
            borrow = getattr(order, 'borrow_order', None)
            if borrow is None:
                raise serializers.ValidationError('Đơn mượn không tồn tại.')
            target = {'sale_listing': None, 'lend_listing': borrow.lend_listing}
        review, created = Review.objects.get_or_create(
            order=order,
            reviewer=request.user,
            defaults={
                **target,
                'rating': serializer.validated_data['rating'],
                'comment': serializer.validated_data.get('comment'),
                'created_at': timezone.now(),
                'updated_at': timezone.now(),
            },
        )
        if not created:
            review.rating = serializer.validated_data['rating']
            review.comment = serializer.validated_data.get('comment')
            review.updated_at = timezone.now()
            review.save(update_fields=['rating', 'comment', 'updated_at'])
        return Response({
            'id': review.id,
            'order_id': review.order_id,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ReviewInputSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True)


class ReturnCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
        )
        if request.user.id != order.buyer_id:
            raise PermissionDenied('Chỉ người mua mới có thể yêu cầu trả hàng.')
        serializer = ReturnInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = get_object_or_404(
            order.sale_items,
            pk=serializer.validated_data['sale_order_item_id'],
        )
        now = timezone.now()
        return_record = Return.objects.create(
            order=order,
            sale_order_item=item,
            reason=serializer.validated_data['reason'],
            description=serializer.validated_data.get('description'),
            status='REQUESTED',
            requested_by=request.user,
            requested_at=now,
        )
        return Response({
            'id': return_record.id,
            'order_id': return_record.order_id,
            'sale_order_item_id': return_record.sale_order_item_id,
            'status': return_record.status,
            'requested_at': return_record.requested_at,
        }, status=status.HTTP_201_CREATED)


class ReturnInputSerializer(serializers.Serializer):
    sale_order_item_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)


class ReturnActionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, return_id, action):
        return_record = get_object_or_404(
            Return.objects.select_for_update().select_related('order'),
            pk=return_id,
        )
        if request.user.id != return_record.order.seller_id:
            raise PermissionDenied('Chỉ người bán mới có thể xử lý yêu cầu trả hàng.')
        now = timezone.now()
        if action == 'approve' and return_record.status == 'REQUESTED':
            return_record.status = 'APPROVED'
            return_record.approved_at = now
            fields = ['status', 'approved_at']
        elif action == 'reject' and return_record.status == 'REQUESTED':
            return_record.status = 'REJECTED'
            fields = ['status']
        elif action == 'complete' and return_record.status == 'APPROVED':
            return_record.status = 'COMPLETED'
            return_record.completed_at = now
            fields = ['status', 'completed_at']
        else:
            raise serializers.ValidationError(
                'Thao tác trả hàng không hợp lệ ở trạng thái hiện tại.',
            )
        return_record.save(update_fields=fields)
        return Response({
            'id': return_record.id,
            'status': return_record.status,
            'approved_at': return_record.approved_at,
            'completed_at': return_record.completed_at,
        })


class RefundCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
        )
        if request.user.id != order.buyer_id:
            raise PermissionDenied('Chỉ người mua mới có thể yêu cầu hoàn tiền.')
        serializer = RefundInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_object_or_404(
            Payment.objects.select_for_update(),
            pk=serializer.validated_data['payment_id'],
            order=order,
        )
        amount = serializer.validated_data['amount']
        idempotency_key = serializer.validated_data['idempotency_key']
        item = None
        borrow_order = None
        return_record = None
        if serializer.validated_data.get('sale_order_item_id') is not None:
            item = get_object_or_404(
                order.sale_items,
                pk=serializer.validated_data['sale_order_item_id'],
            )
        if serializer.validated_data.get('borrow_order_id') is not None:
            borrow_order = get_object_or_404(
                BorrowOrder,
                pk=serializer.validated_data['borrow_order_id'],
                order=order,
            )
        if serializer.validated_data.get('return_id') is not None:
            return_record = get_object_or_404(
                Return,
                pk=serializer.validated_data['return_id'],
                order=order,
            )
            if item is not None and item.id != return_record.sale_order_item_id:
                raise serializers.ValidationError(
                    'Mặt hàng không khớp với yêu cầu trả hàng.',
                )
            if return_record.status not in ('APPROVED', 'COMPLETED'):
                raise serializers.ValidationError(
                    'Yêu cầu trả hàng cần được người bán chấp thuận trước khi hoàn tiền.',
                )
            item = return_record.sale_order_item
        existing = Refund.objects.select_for_update().filter(
            provider=payment.provider,
            idempotency_key=idempotency_key,
        ).first()
        if existing is not None:
            existing_targets = (
                existing.sale_order_item_id,
                existing.borrow_order_id,
                existing.return_record_id,
            )
            requested_targets = (
                item.id if item is not None else None,
                borrow_order.id if borrow_order is not None else None,
                return_record.id if return_record is not None else None,
            )
            if (
                existing.order_id != order.id
                or existing.payment_id != payment.id
                or existing.amount != amount
                or existing.reason != serializer.validated_data['reason']
                or existing_targets != requested_targets
            ):
                raise serializers.ValidationError(
                    'Idempotency key đã được sử dụng cho yêu cầu khác.',
                )
            return Response({
                'id': existing.id,
                'order_id': existing.order_id,
                'payment_id': existing.payment_id,
                'amount': str(existing.amount),
                'status': existing.status,
            })

        if payment.status != 'PAID':
            raise serializers.ValidationError(
                'Chỉ khoản thanh toán đã thành công mới được yêu cầu hoàn tiền.',
            )
        if amount > payment.amount:
            raise serializers.ValidationError('Số tiền hoàn vượt quá số tiền đã thanh toán.')
        previous_refunds = Refund.objects.filter(
            payment=payment,
            status__in=('REQUESTED', 'APPROVED', 'COMPLETED'),
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if previous_refunds + amount > payment.amount:
            raise serializers.ValidationError(
                'Tổng các yêu cầu hoàn tiền vượt quá số tiền đã thanh toán.',
            )
        now = timezone.now()
        refund = Refund.objects.create(
            order=order,
            payment=payment,
            sale_order_item=item,
            borrow_order=borrow_order,
            return_record=return_record,
            provider=payment.provider,
            idempotency_key=serializer.validated_data['idempotency_key'],
            reason=serializer.validated_data['reason'],
            amount=amount,
            currency=payment.currency,
            status='REQUESTED',
            requested_by=request.user,
            requested_at=now,
            created_at=now,
            updated_at=now,
        )
        return Response({
            'id': refund.id,
            'order_id': refund.order_id,
            'payment_id': refund.payment_id,
            'amount': str(refund.amount),
            'status': refund.status,
        }, status=status.HTTP_201_CREATED)


class RefundInputSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)
    sale_order_item_id = serializers.IntegerField(required=False, min_value=1)
    borrow_order_id = serializers.IntegerField(required=False, min_value=1)
    return_id = serializers.IntegerField(required=False, min_value=1)
    idempotency_key = serializers.CharField(max_length=128, allow_blank=False, trim_whitespace=True)
    reason = serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True)
    amount = serializers.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal('0.0001'))

    def validate(self, attrs):
        target_fields = ('sale_order_item_id', 'borrow_order_id', 'return_id')
        if sum(attrs.get(name) is not None for name in target_fields) != 1:
            raise serializers.ValidationError(
                'Yêu cầu hoàn tiền phải xác định chính xác một đối tượng.',
            )
        return attrs

def checkout_payload(checkout):
    orders = list(checkout.orders.prefetch_related('payments').order_by('id'))
    return {
        'id': checkout.id,
        'checkout_code': checkout.checkout_code,
        'status': checkout.status,
        'subtotal': str(checkout.subtotal),
        'shipping_total': str(checkout.shipping_total),
        'total_amount': str(checkout.total_amount),
        'currency': checkout.currency,
        'orders': [
            {
                'id': order.id,
                'order_code': order.order_code,
                'order_type': order.order_type,
                'status': order.status,
                'total_amount': str(order.total_amount),
                'payment_status': next(
                    (payment.status for payment in order.payments.all()),
                    None,
                ),
            }
            for order in orders
        ],
    }


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Order.objects.filter(
            Q(buyer=request.user) | Q(seller=request.user),
        ).prefetch_related(
            'sale_items',
            Prefetch('payments', queryset=Payment.objects.order_by('-created_at', '-id')),
        ).order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            {
                'id': order.id,
                'order_code': order.order_code,
                'order_type': order.order_type,
                'status': order.status,
                'total_amount': str(order.total_amount),
                'currency': order.currency,
                'created_at': order.created_at,
                'item_titles': [item.title_snapshot for item in order.sale_items.all()],
                'payment_status': next(
                    (payment.status for payment in order.payments.all()),
                    None,
                ),
                'recipient_name': order.shipping_address_snapshot.get('recipient_name'),
            }
            for order in page
        ])


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.prefetch_related(
                'sale_items',
                'payments',
                'shipments__tracking_events',
            ),
            pk=order_id,
        )
        if request.user.id not in (order.buyer_id, order.seller_id):
            raise PermissionDenied('Bạn không có quyền xem đơn hàng này.')
        data = {
            'id': order.id,
            'order_code': order.order_code,
            'order_type': order.order_type,
            'status': order.status,
            'total_amount': str(order.total_amount),
            'currency': order.currency,
            'created_at': order.created_at,
            'shipping_address': order.shipping_address_snapshot,
            'items': [
                {
                    'id': item.id,
                    'title': item.title_snapshot,
                    'condition': item.condition_snapshot,
                    'unit_price': str(item.unit_price),
                }
                for item in order.sale_items.all()
            ],
            'payments': [
                {'id': payment.id, 'status': payment.status, 'amount': str(payment.amount)}
                for payment in order.payments.all()
            ],
            'shipments': [
                {
                    'id': shipment.id,
                    'status': shipment.status,
                    'tracking_code': shipment.tracking_code,
                    'tracking': [
                        {
                            'status': event.status,
                            'location': event.location,
                            'description': event.description,
                            'occurred_at': event.occurred_at,
                        }
                        for event in shipment.tracking_events.all()
                    ],
                }
                for shipment in order.shipments.all()
            ],
        }
        if order.order_type == 'BORROW':
            borrow = getattr(order, 'borrow_order', None)
            data['borrow'] = {
                'id': borrow.id,
                'status': borrow.status,
                'expected_start_at': borrow.expected_start_at,
                'expected_return_at': borrow.expected_return_at,
                'actual_start_at': borrow.actual_start_at,
                'actual_return_at': borrow.actual_return_at,
            }
        return Response(data)


class OrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_for_update().select_related('checkout_group'),
            pk=order_id,
        )
        if request.user.id != order.buyer_id:
            raise PermissionDenied('Chỉ người mua mới có thể hủy đơn hàng.')
        if order.status != 'PENDING_PAYMENT':
            raise serializers.ValidationError('Chỉ đơn chưa thanh toán mới có thể hủy.')
        if order.payments.filter(status='PAID').exists():
            raise serializers.ValidationError('Đơn đã thanh toán không thể hủy theo luồng này.')
        now = timezone.now()
        if order.order_type == 'BORROW':
            borrow = get_object_or_404(BorrowOrder, order=order)
            transition_borrow_order(borrow.id, request.user, 'cancel')
        else:
            for item in order.sale_items.select_related(
                'sale_listing', 'book',
            ).select_for_update():
                listing_status = (
                    'EXPIRED'
                    if item.sale_listing.expires_at and item.sale_listing.expires_at <= now
                    else 'ACTIVE'
                )
                item.sale_listing.status = listing_status
                item.sale_listing.updated_at = now
                item.sale_listing.save(update_fields=['status', 'updated_at'])
                item.book.status = 'AVAILABLE' if listing_status == 'ACTIVE' else 'UNAVAILABLE'
                item.book.updated_at = now
                item.book.save(update_fields=['status', 'updated_at'])
            order.status = 'CANCELLED'
            order.updated_at = now
            order.save(update_fields=['status', 'updated_at'])

        if not order.checkout_group.orders.exclude(status__in=('CANCELLED', 'REJECTED')).exists():
            order.checkout_group.status = 'CANCELLED'
            order.checkout_group.updated_at = now
            order.checkout_group.save(update_fields=['status', 'updated_at'])
        return Response({'id': order.id, 'status': 'CANCELLED'})


class BorrowOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = BorrowOrder.objects.filter(
            Q(borrower=request.user) | Q(lender=request.user),
        ).order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            {
                'id': borrow.id,
                'order_id': borrow.order_id,
                'lend_listing_id': borrow.lend_listing_id,
                'lender_id': borrow.lender_id,
                'borrower_id': borrow.borrower_id,
                'status': borrow.status,
                'expected_start_at': borrow.expected_start_at,
                'expected_return_at': borrow.expected_return_at,
                'actual_start_at': borrow.actual_start_at,
                'actual_return_at': borrow.actual_return_at,
            }
            for borrow in page
        ])


class BorrowOrderActionView(APIView):
    permission_classes = [IsAuthenticated]
    ACTIONS = {
        'confirm', 'reject', 'ready', 'start', 'request-return', 'return',
        'complete', 'cancel',
    }

    def post(self, request, borrow_order_id, action):
        if action not in self.ACTIONS:
            raise serializers.ValidationError({'action': 'Thao tác không hợp lệ.'})
        borrow = get_object_or_404(BorrowOrder, pk=borrow_order_id)
        borrow = transition_borrow_order(
            borrow.id,
            request.user,
            action.replace('-', '_'),
        )
        return Response({
            'id': borrow.id,
            'status': borrow.status,
            'expected_start_at': borrow.expected_start_at,
            'expected_return_at': borrow.expected_return_at,
            'actual_start_at': borrow.actual_start_at,
            'actual_return_at': borrow.actual_return_at,
        })


class PaymentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        if request.user.id not in (order.buyer_id, order.seller_id):
            raise PermissionDenied('Bạn không có quyền xem thanh toán này.')
        return Response([
            {
                'id': payment.id,
                'order_id': payment.order_id,
                'amount': str(payment.amount),
                'platform_fee_rate': str(payment.platform_fee_rate),
                'platform_fee': str(payment.platform_fee),
                'seller_amount': str(payment.seller_amount),
                'status': payment.status,
                'paid_at': payment.paid_at,
            }
            for payment in order.payments.order_by('-created_at', '-id')
        ])

    @transaction.atomic
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
        )
        if request.user.id != order.buyer_id:
            raise PermissionDenied('Chỉ người mua mới có thể khởi tạo thanh toán.')
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            fee_rate = Decimal(getattr(settings, 'PASSBOOK_PLATFORM_FEE_RATE', '0'))
        except (InvalidOperation, ValueError) as exc:
            raise serializers.ValidationError('Cấu hình tỷ lệ phí không hợp lệ.') from exc
        try:
            provider = get_payment_provider(data['provider'])
        except PaymentProviderUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        split = calculate_payment_split(order.total_amount, fee_rate)
        now = timezone.now()
        provider_reference = provider.create_payment_intent(
            data['idempotency_key'],
            split['amount'],
            order.currency,
        )
        payment, created = Payment.objects.get_or_create(
            provider=data['provider'],
            idempotency_key=data['idempotency_key'],
            defaults={
                'checkout_group': order.checkout_group,
                'order': order,
                'payer': request.user,
                'payment_method': data['payment_method'],
                'payment_purpose': 'CHECKOUT',
                'provider_transaction_code': provider_reference,
                'amount': split['amount'],
                'platform_fee_rate': split['platform_fee_rate'],
                'platform_fee': split['platform_fee'],
                'seller_amount': split['seller_amount'],
                'currency': order.currency,
                'status': 'PENDING',
                'created_at': now,
                'updated_at': now,
            },
        )
        if not created and (
            payment.order_id != order.id
            or payment.payer_id != request.user.id
        ):
            raise serializers.ValidationError(
                'Idempotency key đã được sử dụng cho khoản thanh toán khác.',
            )
        return Response(
            payment_payload(payment),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FakePaymentTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, payment_id):
        if not fake_payments_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user.role != 'ADMIN':
            raise PermissionDenied('Chỉ quản trị viên mới được mô phỏng thanh toán.')
        serializer = FakePaymentTransitionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = transition_fake_payment(
                payment_id,
                serializer.validated_data['status'],
            )
        except PaymentProviderUnavailable as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(payment_payload(payment))


class FakePaymentTransitionInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=('PENDING', 'PAID', 'FAILED', 'CANCELLED'))


class FakeRefundTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, refund_id):
        if not fake_payments_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user.role != 'ADMIN':
            raise PermissionDenied('Chỉ quản trị viên mới được mô phỏng hoàn tiền.')
        serializer = FakeRefundTransitionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund = transition_fake_refund(
                refund_id,
                serializer.validated_data['status'],
            )
        except PaymentProviderUnavailable as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response({
            'id': refund.id,
            'payment_id': refund.payment_id,
            'amount': str(refund.amount),
            'status': refund.status,
        })


class FakeRefundTransitionInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=('COMPLETED', 'FAILED'))


class PaymentInputSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True)
    payment_method = serializers.CharField(max_length=30, allow_blank=False, trim_whitespace=True)
    idempotency_key = serializers.CharField(max_length=128, allow_blank=False, trim_whitespace=True)


def payment_payload(payment):
    return {
        'id': payment.id,
        'order_id': payment.order_id,
        'amount': str(payment.amount),
        'platform_fee_rate': str(payment.platform_fee_rate),
        'platform_fee': str(payment.platform_fee),
        'seller_amount': str(payment.seller_amount),
        'status': payment.status,
        'paid_at': payment.paid_at,
    }


class ShipmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        if request.user.id not in (order.buyer_id, order.seller_id):
            raise PermissionDenied('Bạn không có quyền xem thông tin giao hàng.')
        shipments = order.shipments.prefetch_related('tracking_events').order_by('id')
        return Response([
            {
                'id': shipment.id,
                'status': shipment.status,
                'carrier': shipment.carrier,
                'tracking_code': shipment.tracking_code,
                'tracking': [
                    {
                        'status': entry.status,
                        'location': entry.location,
                        'description': entry.description,
                        'occurred_at': entry.occurred_at,
                    }
                    for entry in shipment.tracking_events.all()
                ],
            }
            for shipment in shipments
        ])

    @transaction.atomic
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
        )
        if request.user.id != order.seller_id:
            raise PermissionDenied('Chỉ người bán mới có thể tạo thông tin giao hàng.')
        if not order.payments.filter(status='PAID').exists():
            raise serializers.ValidationError('Chỉ đơn đã thanh toán mới được giao.')
        serializer = ShipmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        shipment = Shipment.objects.create(
            order=order,
            carrier=serializer.validated_data.get('carrier'),
            tracking_code=serializer.validated_data.get('tracking_code'),
            shipping_fee=Decimal('0'),
            status='SHIPPED',
            shipped_at=now,
            currency='VND',
            created_at=now,
            updated_at=now,
        )
        ShipmentTracking.objects.create(
            shipment=shipment,
            status='SHIPPED',
            location=serializer.validated_data.get('location'),
            description='Đơn hàng đã được bàn giao cho đơn vị vận chuyển.',
            occurred_at=now,
            created_at=now,
        )
        return Response(
            {'id': shipment.id, 'status': shipment.status, 'tracking_code': shipment.tracking_code},
            status=status.HTTP_201_CREATED,
        )


class ShipmentTrackingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.select_related('order'),
            pk=shipment_id,
        )
        if request.user.id != shipment.order.seller_id:
            raise PermissionDenied('Chỉ người bán mới có thể cập nhật theo dõi giao hàng.')
        serializer = ShipmentTrackingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        data = serializer.validated_data
        occurred_at = data.get('occurred_at') or now
        latest = shipment.tracking_events.order_by(
            '-occurred_at', '-id',
        ).first()
        if latest is not None and occurred_at < latest.occurred_at:
            raise serializers.ValidationError(
                {'occurred_at': 'Thời điểm sự kiện không được trước sự kiện gần nhất.'},
            )
        if shipment.status == 'DELIVERED' and data['status'] != 'DELIVERED':
            raise serializers.ValidationError(
                'Không thể cập nhật trạng thái sau khi giao hàng hoàn tất.',
            )
        with transaction.atomic():
            event = ShipmentTracking.objects.create(
                shipment=shipment,
                status=data['status'],
                location=data.get('location'),
                description=data.get('description'),
                occurred_at=occurred_at,
                created_at=now,
            )
            shipment.status = data['status']
            if data['status'] == 'SHIPPED' and shipment.shipped_at is None:
                shipment.shipped_at = event.occurred_at
            if data['status'] == 'DELIVERED':
                shipment.delivered_at = event.occurred_at
            shipment.updated_at = now
            shipment.save(update_fields=[
                'status', 'shipped_at', 'delivered_at', 'updated_at',
            ])
        return Response({
            'id': event.id,
            'shipment_id': shipment.id,
            'status': event.status,
            'location': event.location,
            'description': event.description,
            'occurred_at': event.occurred_at,
        }, status=status.HTTP_201_CREATED)


class ShipmentInputSerializer(serializers.Serializer):
    carrier = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_code = serializers.CharField(max_length=150, required=False, allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)


class ShipmentTrackingInputSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=30, allow_blank=False, trim_whitespace=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    occurred_at = serializers.DateTimeField(required=False)

    def validate_status(self, value):
        normalized = value.upper()
        allowed = {
            'SHIPPED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY',
            'DELIVERED', 'EXCEPTION', 'RETURNED',
        }
        if normalized not in allowed:
            raise serializers.ValidationError('Trạng thái vận chuyển không hợp lệ.')
        return normalized
