from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone

from books.models import (
    BookRequest,
    BookReservation,
    BookWork,
    BorrowOrder,
    Cart,
    Category,
    Favorite,
    LendListing,
    Order,
    Payment,
    Refund,
    Return,
    Review,
    SaleListing,
    Shipment,
)
from messaging.models import Conversation, Message
from notifications.models import Notification
from reports.models import Report
from users.models import Subject, University, User


PERIOD_TRUNCATIONS = {
    'day': TruncDate,
    'week': TruncWeek,
    'month': TruncMonth,
    'year': TruncYear,
}
PERIOD_DELTAS = {
    'day': timedelta(days=1),
    'week': timedelta(days=7),
    'month': timedelta(days=30),
    'year': timedelta(days=365),
}


def _status_counts(queryset):
    return {
        row['status']: row['total']
        for row in queryset.values('status').annotate(total=Count('pk'))
    }


def _status_section(queryset, **aliases):
    statuses = _status_counts(queryset)
    return {
        'total': sum(statuses.values()),
        'by_status': statuses,
        **{key: statuses.get(status, 0) for key, status in aliases.items()},
    }


def _aware_start(day):
    value = datetime.combine(day, time.min)
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _period_dates(now=None):
    now = now or timezone.localtime()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    return today, week_start, month_start


def _month_after(day):
    if day.month == 12:
        return day.replace(year=day.year + 1, month=1, day=1)
    return day.replace(month=day.month + 1, day=1)


def _created_window_counts(queryset, field='created_at'):
    today, week_start, month_start = _period_dates()
    return queryset.aggregate(
        today=Count('pk', filter=Q(
            **{f'{field}__gte': _aware_start(today), f'{field}__lt': _aware_start(today + timedelta(days=1))},
        )),
        this_week=Count('pk', filter=Q(
            **{f'{field}__gte': _aware_start(week_start), f'{field}__lt': _aware_start(week_start + timedelta(days=7))},
        )),
        this_month=Count('pk', filter=Q(
            **{f'{field}__gte': _aware_start(month_start), f'{field}__lt': _aware_start(_month_after(month_start))},
        )),
    )


def _merge_status_counts(*querysets):
    result = {}
    for queryset in querysets:
        for status, count in _status_counts(queryset).items():
            result[status] = result.get(status, 0) + count
    return result


def _named_counts(queryset, field, limit=10):
    return list(
        queryset.values(field)
        .annotate(total=Count('pk'))
        .order_by('-total', field)[:limit]
    )


def _top_users(querysets, limit=10):
    totals = {}
    names = {}
    for queryset in querysets:
        for row in queryset:
            user_id = row['user_id']
            totals[user_id] = totals.get(user_id, 0) + row['total']
            names[user_id] = row['name']
    return [
        {'user_id': user_id, 'name': names[user_id], 'total': count}
        for user_id, count in sorted(
            totals.items(),
            key=lambda item: (-item[1], str(names[item[0]]).lower(), item[0]),
        )[:limit]
    ]


def _grouped_listing_counts(querysets, field, label_field):
    totals = {}
    for item in querysets:
        if isinstance(item, tuple):
            queryset, item_field, item_label_field = item
        else:
            queryset, item_field, item_label_field = item, field, label_field
        for row in queryset.values(
            item_id=F(item_field),
            item_name=F(item_label_field),
        ).annotate(total=Count('pk', distinct=True)):
            key = row['item_id']
            item = totals.setdefault(
                key,
                {'id': key, 'name': row['item_name'], 'total': 0},
            )
            item['total'] += row['total']
    return sorted(totals.values(), key=lambda item: (-item['total'], item['name'] or ''))


def _listings():
    return SaleListing.objects.all(), LendListing.objects.all()


def users_dashboard():
    statuses = _status_counts(User.objects.all())
    created = _created_window_counts(User.objects.all())
    by_university = list(
        User.objects.values('university_id', 'university__name')
        .annotate(total=Count('pk'))
        .order_by('-total', 'university__name')
    )
    sale_users = _normalize_user_rows(
        SaleListing.objects.values('seller_id', 'seller__full_name').annotate(total=Count('pk')),
        'seller_id',
        'seller__full_name',
    )
    lend_users = _normalize_user_rows(
        LendListing.objects.values('lender_id', 'lender__full_name').annotate(total=Count('pk')),
        'lender_id',
        'lender__full_name',
    )
    buyer_orders = Order.objects.exclude(buyer_id__isnull=True).values(
        'buyer_id',
        'buyer__full_name',
    ).annotate(total=Count('pk'))
    seller_orders = Order.objects.exclude(seller_id__isnull=True).values(
        'seller_id',
        'seller__full_name',
    ).annotate(total=Count('pk'))
    reports = Report.objects.exclude(reported_user_id__isnull=True).values(
        'reported_user_id',
        'reported_user__full_name',
    ).annotate(total=Count('pk'))
    return {
        'total': sum(statuses.values()),
        'active': statuses.get('ACTIVE', 0),
        'locked_inactive': statuses.get('BLOCKED', 0),
        'by_status': statuses,
        'created_today': created['today'],
        'created_this_week': created['this_week'],
        'created_this_month': created['this_month'],
        'by_university': by_university,
        'most_listings': _top_users([sale_users, lend_users]),
        'most_transactions': _top_users([
            _normalize_user_rows(buyer_orders, 'buyer_id', 'buyer__full_name'),
            _normalize_user_rows(seller_orders, 'seller_id', 'seller__full_name'),
        ]),
        'most_reports': [
            {
                'user_id': row['reported_user_id'],
                'name': row['reported_user__full_name'],
                'total': row['total'],
            }
            for row in reports.order_by('-total', 'reported_user_id')[:10]
        ],
    }


def _normalize_user_rows(queryset, id_field, name_field):
    return [
        {
            'user_id': row[id_field],
            'name': row[name_field],
            'total': row['total'],
        }
        for row in queryset
    ]


def marketplace_dashboard():
    sale, lend = _listings()
    statuses = _merge_status_counts(sale, lend)
    sale_status = _status_counts(sale)
    lend_status = _status_counts(lend)
    created_sale = _created_window_counts(sale)
    created_lend = _created_window_counts(lend)
    category_field = 'book__book_edition__book_work__category_id'
    category_name = 'book__book_edition__book_work__category__name'
    subject_field = 'book__book_edition__book_work__subject_links__subject_id'
    subject_name = 'book__book_edition__book_work__subject_links__subject__name'
    university_field_sale = 'seller__university_id'
    university_name_sale = 'seller__university__name'
    university_field_lend = 'lender__university_id'
    university_name_lend = 'lender__university__name'
    return {
        'total': sum(statuses.values()),
        'sale': sum(sale_status.values()),
        'borrow': sum(lend_status.values()),
        'by_status': statuses,
        'active': statuses.get('ACTIVE', 0),
        'pending': statuses.get('PENDING', 0),
        'sold': statuses.get('SOLD', 0),
        'rejected': statuses.get('REJECTED', 0),
        'created_today': created_sale['today'] + created_lend['today'],
        'created_this_month': created_sale['this_month'] + created_lend['this_month'],
        'by_category': _grouped_listing_counts(
            [sale, lend], category_field, category_name,
        ),
        'by_subject': _grouped_listing_counts(
            [sale, lend], subject_field, subject_name,
        ),
        'by_university': _grouped_listing_counts(
            [
                (sale, university_field_sale, university_name_sale),
                (lend, university_field_lend, university_name_lend),
            ],
            'university_id',
            'university__name',
        ),
    }


def commerce_dashboard():
    sale_orders = Order.objects.filter(order_type='SALE')
    statuses = _status_counts(sale_orders)
    created = _created_window_counts(sale_orders)
    finance = _sale_financial_metrics()
    revenue = sale_orders.filter(status='COMPLETED').aggregate(
        average=Avg('subtotal'),
    )
    shipment_statuses = sale_orders.aggregate(
        shipping=Count(
            'pk',
            filter=Q(shipments__status__in=('PENDING', 'PICKED_UP', 'IN_TRANSIT')),
            distinct=True,
        ),
        delivered=Count(
            'pk',
            filter=Q(shipments__status='DELIVERED'),
            distinct=True,
        ),
    )
    return {
        'total_orders': sale_orders.count(),
        'by_status': statuses,
        'completed': statuses.get('COMPLETED', 0),
        'pending': sum(value for key, value in statuses.items() if key.startswith('PENDING')),
        'shipping': shipment_statuses['shipping'],
        'delivered': shipment_statuses['delivered'],
        'cancelled': statuses.get('CANCELLED', 0),
        'orders_today': created['today'],
        'orders_this_month': created['this_month'],
        'gmv': finance['gmv'],
        'platform_revenue': finance['platform_revenue'],
        'seller_earnings': finance['seller_earnings'],
        'average_order_value': revenue['average'] or 0,
        'gmv_definition': 'Net SALE merchandise subtotal after completed refunds; BORROW excluded.',
    }


def _sale_financial_metrics():
    successful = Payment.objects.filter(
        order__order_type='SALE',
        status__in=('PAID', 'REFUNDED'),
    )
    totals = successful.aggregate(
        gmv=Sum('amount'),
        platform_revenue=Sum('platform_fee'),
        seller_earnings=Sum('seller_amount'),
        customer_total=Sum('amount'),
    )
    allocation_type = DecimalField(max_digits=38, decimal_places=8)
    completed_refunds = Refund.objects.filter(
        order__order_type='SALE',
        status='COMPLETED',
        payment__status__in=('PAID', 'REFUNDED'),
    ).aggregate(
        gmv=Sum(ExpressionWrapper(
            F('amount'),
            output_field=allocation_type,
        )),
        platform_revenue=Sum(ExpressionWrapper(
            F('amount') * F('payment__platform_fee') / F('payment__amount'),
            output_field=allocation_type,
        )),
        customer_total=Sum('amount'),
    )
    zero = Decimal('0')
    return {
        'gmv': (totals['gmv'] or zero) - (completed_refunds['gmv'] or zero),
        'platform_revenue': (
            (totals['platform_revenue'] or zero)
            - (completed_refunds['platform_revenue'] or zero)
        ),
        'seller_earnings': (totals['seller_earnings'] or zero) - (
            completed_refunds['gmv'] or zero
        ) * (Decimal('1') - (Decimal('0.10'))),
        'customer_total': (totals['customer_total'] or zero) - (completed_refunds['customer_total'] or zero),
    }


def borrow_dashboard():
    bookings = BorrowOrder.objects.all()
    statuses = _status_counts(bookings)
    active = statuses.get('ACTIVE', 0)
    return_trackings = bookings.exclude(
        return_tracking_code__isnull=True,
    ).exclude(return_tracking_code='').values('return_tracking_code')
    shipping_borrow = Shipment.objects.filter(
        order_id__in=bookings.values('order_id'),
        status__in=('PENDING', 'PICKED_UP', 'IN_TRANSIT'),
    ).exclude(tracking_code__in=return_trackings).values('order_id').distinct().count()
    return {
        'total_reservations': BookReservation.objects.count(),
        'reservations_by_status': _status_counts(BookReservation.objects.all()),
        'pending_reservations': BookReservation.objects.filter(status='PENDING').count(),
        'total_borrow_orders': sum(statuses.values()),
        'by_status': statuses,
        'pending': statuses.get('PENDING', 0),
        'active_borrow': active,
        'shipping_borrow': shipping_borrow,
        'overdue_borrow': statuses.get('OVERDUE', 0),
        'return_requested': statuses.get('RETURN_REQUESTED', 0),
        'returned': statuses.get('RETURNED', 0),
        'completed': statuses.get('COMPLETED', 0),
        'cancelled': statuses.get('CANCELLED', 0),
    }


def shipping_dashboard():
    shipments = Shipment.objects.all()
    statuses = _status_counts(shipments)
    return_shipments = shipments.filter(
        tracking_code__in=BorrowOrder.objects.exclude(
            return_tracking_code__isnull=True,
        ).exclude(return_tracking_code='').values('return_tracking_code'),
    )
    borrow_orders = BorrowOrder.objects.filter(order_id__in=shipments.values('order_id'))
    borrow_delivery = shipments.filter(order_id__in=borrow_orders.values('order_id')).exclude(
        pk__in=return_shipments.values('pk'),
    )
    return {
        'total': sum(statuses.values()),
        'by_status': statuses,
        'pending': statuses.get('PENDING', 0),
        'picked_up': statuses.get('PICKED_UP', 0),
        'in_transit': statuses.get('IN_TRANSIT', 0),
        'delivered': statuses.get('DELIVERED', 0),
        'failed': statuses.get('FAILED', 0),
        'borrow_delivery': borrow_delivery.count(),
        'return_shipment': return_shipments.count(),
        'return_direction': 'BORROWER_TO_OWNER',
        'return_shipment_statuses': _status_counts(return_shipments),
    }


def returns_dashboard():
    borrow_rows = list(
        BorrowOrder.objects.values('status', 'return_status')
        .annotate(total=Count('pk'))
    )
    borrow_statuses = {}
    return_statuses = {}
    for row in borrow_rows:
        borrow_statuses[row['status']] = borrow_statuses.get(row['status'], 0) + row['total']
        if row['return_status']:
            return_statuses[row['return_status']] = (
                return_statuses.get(row['return_status'], 0) + row['total']
            )
    sale_return_statuses = _status_counts(Return.objects.all())
    sale_refunds = Refund.objects.filter(order__order_type='SALE')
    refund_statuses = _status_counts(sale_refunds)
    return {
        'borrow_return': {
            'return_requested': borrow_statuses.get('RETURN_REQUESTED', 0),
            'by_status': return_statuses,
            'return_shipment': return_statuses.get('SHIPPING', 0),
            'delivered': return_statuses.get('DELIVERED', 0),
            'owner_confirmation_pending': sum(
                row['total'] for row in borrow_rows
                if row['status'] == 'RETURNED' and row['return_status'] == 'DELIVERED'
            ),
            'completed': sum(
                row['total'] for row in borrow_rows
                if row['status'] == 'COMPLETED' and row['return_status'] == 'COMPLETED'
            ),
            'shipment_direction': 'BORROWER_TO_OWNER',
        },
        'sale_return': {
            'available': True,
            'total': sum(sale_return_statuses.values()),
            'by_status': sale_return_statuses,
            'refund_pending': refund_statuses.get('REQUESTED', 0),
            'refunded': refund_statuses.get('COMPLETED', 0),
            'refunds_by_status': refund_statuses,
        },
    }


def payments_dashboard():
    payments = Payment.objects.all()
    statuses = _status_counts(payments)
    today, _week_start, month_start = _period_dates()
    paid = payments.filter(status__in=('PAID', 'REFUNDED'))
    amounts = paid.aggregate(
        total=Sum('amount'),
        today=Sum('amount', filter=Q(
            paid_at__gte=_aware_start(today),
            paid_at__lt=_aware_start(today + timedelta(days=1)),
        )),
        this_month=Sum('amount', filter=Q(
            paid_at__gte=_aware_start(month_start),
            paid_at__lt=_aware_start(_month_after(month_start)),
        )),
    )
    return {
        'total': sum(statuses.values()),
        'by_status': statuses,
        'paid': statuses.get('PAID', 0),
        'pending': statuses.get('PENDING', 0),
        'failed': statuses.get('FAILED', 0),
        'cancelled': statuses.get('CANCELLED', 0),
        'refunded': statuses.get('REFUNDED', 0),
        'total_amount': _sale_financial_metrics()['customer_total'],
        'amount_today': amounts['today'] or 0,
        'amount_this_month': amounts['this_month'] or 0,
        **_sale_financial_metrics(),
    }


def reports_dashboard():
    reports = Report.objects.all()
    statuses = _status_counts(reports)
    reason_counts = list(
        reports.values('reason').annotate(total=Count('pk')).order_by('-total', 'reason')
    )
    reported_users = list(
        reports.exclude(reported_user_id__isnull=True)
        .values('reported_user_id', 'reported_user__full_name')
        .annotate(total=Count('pk')).order_by('-total', 'reported_user_id')[:10]
    )
    listing_counts = []
    for field, label in (
        ('sale_listing_id', 'sale_listing'),
        ('lend_listing_id', 'lend_listing'),
    ):
        listing_counts.extend(
            {
                'listing_type': label,
                'listing_id': row[field],
                'total': row['total'],
            }
            for row in reports.exclude(**{f'{field}__isnull': True})
            .values(field).annotate(total=Count('pk')).order_by('-total', field)[:10]
        )
    return {
        'total': sum(statuses.values()),
        'pending': statuses.get('OPEN', 0),
        'reviewing': statuses.get('IN_REVIEW', 0),
        'resolved': statuses.get('RESOLVED', 0) + statuses.get('REJECTED', 0),
        'by_status': statuses,
        'by_type': reason_counts,
        'most_reported_users': reported_users,
        'most_reported_listings': sorted(
            listing_counts, key=lambda item: (-item['total'], item['listing_type'], item['listing_id']),
        )[:10],
        'time_series': {
            'by_day': _time_series(reports, 'created_at', 'day'),
            'by_month': _time_series(reports, 'created_at', 'month'),
        },
    }


def messaging_dashboard():
    today, _week_start, _month_start = _period_dates()
    messages = Message.objects.all()
    return {
        'total_conversations': Conversation.objects.count(),
        'total_messages': messages.count(),
        'conversations_today': Conversation.objects.filter(
            created_at__gte=_aware_start(today),
        ).count(),
        'messages_today': messages.filter(sent_at__gte=_aware_start(today)).count(),
        'active_conversations_available': False,
        'most_messages_by_user': list(
            messages.values('sender_id', 'sender__full_name')
            .annotate(total=Count('pk'))
            .order_by('-total', 'sender_id')[:10]
        ),
    }


def notifications_dashboard():
    notifications = Notification.objects.all()
    return {
        'total': notifications.count(),
        'today': notifications.filter(created_at__gte=_aware_start(_period_dates()[0])).count(),
        'unread': notifications.filter(is_read=False).count(),
        'by_type': list(
            notifications.values('notification_type')
            .annotate(total=Count('pk')).order_by('-total', 'notification_type')
        ),
    }


def reviews_dashboard():
    reviews = Review.objects.all()
    today, _week_start, month_start = _period_dates()
    distribution = {
        row['rating']: row['total']
        for row in reviews.values('rating').annotate(total=Count('pk'))
    }
    review_summary = reviews.aggregate(
        average=Avg('rating'),
        today=Count('pk', filter=Q(
            created_at__gte=_aware_start(today),
            created_at__lt=_aware_start(today + timedelta(days=1)),
        )),
        this_month=Count('pk', filter=Q(
            created_at__gte=_aware_start(month_start),
            created_at__lt=_aware_start(_month_after(month_start)),
        )),
    )
    return {
        'total': sum(distribution.values()),
        'today': review_summary['today'],
        'this_month': review_summary['this_month'],
        'average_rating': review_summary['average'] or 0,
        'rating_distribution': [
            {'rating': rating, 'total': distribution.get(rating, 0)}
            for rating in range(1, 6)
        ],
        'reported_reviews_available': False,
        'reported_reviews': None,
    }


def favorites_dashboard():
    favorites = Favorite.objects.all()
    groups = []
    for field, label, name_field in (
        ('book_id', 'book', 'book__book_edition__book_work__title'),
        ('sale_listing_id', 'sale_listing', 'sale_listing__title'),
        ('lend_listing_id', 'lend_listing', 'lend_listing__title'),
    ):
        groups.extend(
            {
                'item_type': label,
                'item_id': row['item_id'],
                'title': row['title'],
                'total': row['total'],
            }
            for row in favorites.exclude(**{f'{field}__isnull': True})
            .values(item_id=F(field), title=F(name_field))
            .annotate(total=Count('pk'))
            .order_by('-total', 'item_id')[:10]
        )
    return {
        'total': favorites.count(),
        'today': favorites.filter(created_at__gte=_aware_start(_period_dates()[0])).count(),
        'top_favorited': sorted(groups, key=lambda item: (-item['total'], item['item_type'], item['item_id']))[:10],
        'users_with_most_favorites': list(
            favorites.values('user_id', 'user__full_name')
            .annotate(total=Count('pk')).order_by('-total', 'user_id')[:10]
        ),
    }


def demand_dashboard():
    requests = BookRequest.objects.all()
    totals = {
        row['request_type']: row['total']
        for row in requests.values('request_type').annotate(total=Count('pk'))
    }
    requested_works = list(
        requests.exclude(book_work_id__isnull=True)
        .values('book_work_id', 'book_work__title', 'request_type')
        .annotate(total=Count('pk')).order_by('-total', 'book_work__title')[:10]
    )
    by_category = list(
        requests.exclude(category_id__isnull=True)
        .values('category_id', 'category__name', 'request_type')
        .annotate(total=Count('pk')).order_by('-total', 'category__name')
    )
    by_subject = list(
        requests.exclude(book_work_id__isnull=True)
        .values(
            'book_work__subject_links__subject_id',
            'book_work__subject_links__subject__name',
            'request_type',
        ).annotate(total=Count('pk')).order_by('-total', 'book_work__subject_links__subject__name')
    )
    by_university = list(
        requests.values('user__university_id', 'user__university__name', 'request_type')
        .annotate(total=Count('pk')).order_by('-total', 'user__university__name')
    )
    return {
        'total_buy_requests': totals.get('BUY', 0),
        'total_borrow_requests': totals.get('BORROW', 0),
        'total': sum(totals.values()),
        'by_type': totals,
        'top_requested_books': requested_works,
        'by_category': by_category,
        'by_subject': by_subject,
        'by_university': by_university,
        'hold_or_waiting_list_supported': False,
    }


def catalog_dashboard():
    return {
        'categories': Category.objects.count(),
        'subjects': Subject.objects.count(),
        'universities': University.objects.count(),
        'locations': {'available': False, 'total': None},
        'books_per_category': list(
            BookWork.objects.exclude(category_id__isnull=True)
            .values('category_id', 'category__name')
            .annotate(total=Count('pk')).order_by('-total', 'category__name')
        ),
        'books_per_subject': list(
            BookWork.objects.values(
                'subject_links__subject_id',
                'subject_links__subject__name',
            ).annotate(total=Count('pk', distinct=True))
            .order_by('-total', 'subject_links__subject__name')
        ),
        'books_per_university': list(
            BookWork.objects.values('created_by__university_id', 'created_by__university__name')
            .annotate(total=Count('pk')).order_by('-total', 'created_by__university__name')
        ),
    }


def _time_series(queryset, field, period, start_date=None, end_date=None):
    trunc = PERIOD_TRUNCATIONS[period]
    filters = {}
    if start_date:
        filters[f'{field}__gte'] = _aware_start(start_date)
    elif not end_date:
        filters[f'{field}__gte'] = timezone.now() - PERIOD_DELTAS[period] * 12
    if end_date:
        filters[f'{field}__lt'] = _aware_start(end_date + timedelta(days=1))
    return [
        {'period': row['period'], 'total': row['total']}
        for row in queryset.filter(**filters)
        .annotate(period=trunc(field))
        .values('period')
        .annotate(total=Count('pk'))
        .order_by('period')
    ]


def analytics_dashboard(params):
    period = params.get('period', 'day')
    if period not in PERIOD_TRUNCATIONS:
        return {'error': 'period must be one of: day, week, month, year'}
    try:
        start_date = date.fromisoformat(params['start_date']) if params.get('start_date') else None
        end_date = date.fromisoformat(params['end_date']) if params.get('end_date') else None
    except ValueError:
        return {'error': 'start_date and end_date must use YYYY-MM-DD format'}
    if start_date and end_date and start_date > end_date:
        return {'error': 'start_date must not be after end_date'}

    sale, lend = _listings()
    sale_listings = _time_series(sale, 'created_at', period, start_date, end_date)
    lend_listings = _time_series(lend, 'created_at', period, start_date, end_date)
    orders = _time_series(Order.objects.all(), 'created_at', period, start_date, end_date)
    payments = _time_series(Payment.objects.all(), 'created_at', period, start_date, end_date)
    borrow = _time_series(BorrowOrder.objects.all(), 'created_at', period, start_date, end_date)
    reports = _time_series(Report.objects.all(), 'created_at', period, start_date, end_date)
    sale_returns = _time_series(
        Return.objects.all(), 'requested_at', period, start_date, end_date,
    )
    borrow_returns = _time_series(
        BorrowOrder.objects.exclude(return_requested_at__isnull=True),
        'return_requested_at',
        period,
        start_date,
        end_date,
    )
    return {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'users': _time_series(User.objects.all(), 'created_at', period, start_date, end_date),
        'listings': _merge_series(sale_listings, lend_listings),
        'orders': orders,
        'payments': payments,
        'borrow': borrow,
        'returns': _merge_series(sale_returns, borrow_returns),
        'reports': reports,
    }


def _merge_series(*series):
    totals = {}
    for entries in series:
        for row in entries:
            key = row['period']
            totals[key] = totals.get(key, 0) + row['total']
    return [{'period': key, 'total': totals[key]} for key in sorted(totals)]


def get_dashboard_metrics():
    sale, lend = _listings()
    sale_statuses = _status_counts(sale)
    lend_statuses = _status_counts(lend)
    listing_statuses = dict(sale_statuses)
    for status, total in lend_statuses.items():
        listing_statuses[status] = listing_statuses.get(status, 0) + total
    borrow_statuses = _status_counts(BorrowOrder.objects.all())
    order_statuses = {}
    order_types = {}
    for row in Order.objects.values('order_type', 'status').annotate(total=Count('pk')):
        order_statuses[row['status']] = order_statuses.get(row['status'], 0) + row['total']
        order_types[row['order_type']] = order_types.get(row['order_type'], 0) + row['total']
    created_users = _created_window_counts(User.objects.all())
    finance = _sale_financial_metrics()
    order_metrics = {
        'total': sum(order_statuses.values()),
        'by_status': order_statuses,
        'pending': order_statuses.get('PENDING_PAYMENT', 0),
        'completed': order_statuses.get('COMPLETED', 0),
        'cancelled': order_statuses.get('CANCELLED', 0),
        'sale': order_types.get('SALE', 0),
        'borrow': order_types.get('BORROW', 0),
    }
    payment_metrics = _status_section(
        Payment.objects.all(),
        pending='PENDING',
        paid='PAID',
        failed='FAILED',
        cancelled='CANCELLED',
        refunded='REFUNDED',
    )
    payment_metrics.update({
        'paid_orders': Order.objects.filter(
            order_type='SALE',
            payments__status__in=('PAID', 'REFUNDED'),
        ).distinct().count(),
        'pending_payments': Payment.objects.filter(
            status__in=('PENDING', 'PROCESSING'),
        ).count(),
    })
    shipment_metrics = _status_section(
        Shipment.objects.all(),
        pending='PENDING',
        picked_up='PICKED_UP',
        in_transit='IN_TRANSIT',
        delivered='DELIVERED',
        failed='FAILED',
    )
    shipment_metrics['active'] = Shipment.objects.filter(
        status__in=('PENDING', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY'),
    ).count()
    demand_types = {
        row['request_type']: row['total']
        for row in BookRequest.objects.values('request_type')
        .annotate(total=Count('pk'))
    }
    users = _status_section(
        User.objects.all(),
        active='ACTIVE',
        locked='BLOCKED',
        pending_verification='PENDING_VERIFICATION',
    )
    users.update({
        'created_today': created_users['today'],
        'created_this_month': created_users['this_month'],
    })
    return {
        'users': users,
        'listings': {
            'total': sum(listing_statuses.values()),
            'by_status': listing_statuses,
            'active': listing_statuses.get('ACTIVE', 0),
            'sold': listing_statuses.get('SOLD', 0),
            'draft': listing_statuses.get('DRAFT', 0),
            'pending': listing_statuses.get('PENDING', 0),
            'rejected': listing_statuses.get('REJECTED', 0),
            'pending_status_supported': any(
                'PENDING' == status for model in (SaleListing, LendListing)
                for status, _label in model.STATUS_CHOICES
            ),
            'rejected_status_supported': any(
                'REJECTED' == status for model in (SaleListing, LendListing)
                for status, _label in model.STATUS_CHOICES
            ),
        },
        'lend_listings': {
            'total': sum(lend_statuses.values()),
            'by_status': lend_statuses,
            'active': lend_statuses.get('ACTIVE', 0),
            'on_loan': lend_statuses.get('ON_LOAN', 0),
        },
        'reservations': _status_section(
            BookReservation.objects.all(),
            pending='PENDING', confirmed='CONFIRMED', completed='COMPLETED',
        ),
        'carts': _status_section(Cart.objects.all(), active='ACTIVE'),
        'orders': order_metrics,
        'payments': payment_metrics,
        'finance': finance,
        'refunds': _status_section(
            Refund.objects.all(),
            requested='REQUESTED', pending='REQUESTED',
            completed='COMPLETED', rejected='REJECTED',
        ),
        'returns': _status_section(
            Return.objects.all(),
            requested='REQUESTED', pending='REQUESTED',
            approved='APPROVED', completed='COMPLETED',
        ),
        'shipments': shipment_metrics,
        'reports': _status_section(
            Report.objects.all(),
            open='OPEN', pending='OPEN', in_review='IN_REVIEW', resolved='RESOLVED',
        ),
        'conversations': Conversation.objects.count(),
        'messages': Message.objects.count(),
        'notifications': Notification.objects.count(),
        'favorites': Favorite.objects.count(),
        'reviews': Review.objects.count(),
        'demand': {
            'total_buy_requests': demand_types.get('BUY', 0),
            'total_borrow_requests': demand_types.get('BORROW', 0),
            'by_type': demand_types,
        },
        'borrow': {
            'total': sum(borrow_statuses.values()),
            'by_status': borrow_statuses,
            'pending': borrow_statuses.get('PENDING', 0),
            'active': borrow_statuses.get('ACTIVE', 0),
            'overdue': borrow_statuses.get('OVERDUE', 0),
            'completed': borrow_statuses.get('COMPLETED', 0),
            'return_requested': borrow_statuses.get('RETURN_REQUESTED', 0),
        },
    }


DASHBOARD_SECTIONS = {
    'overview': get_dashboard_metrics,
    'users': users_dashboard,
    'marketplace': marketplace_dashboard,
    'commerce': commerce_dashboard,
    'borrow': borrow_dashboard,
    'shipping': shipping_dashboard,
    'returns': returns_dashboard,
    'payments': payments_dashboard,
    'reports': reports_dashboard,
    'messaging': messaging_dashboard,
    'notifications': notifications_dashboard,
    'reviews': reviews_dashboard,
    'favorites': favorites_dashboard,
    'demand': demand_dashboard,
    'catalog': catalog_dashboard,
}
