from django.db.models import Count

from books.models import (
    BookReservation,
    Cart,
    Favorite,
    LendListing,
    Order,
    Payment,
    Refund,
    Return,
    SaleListing,
    Shipment,
)
from messaging.models import Conversation, Message
from reports.models import Report
from users.models import User


def _status_counts(queryset):
    return {
        row['status']: row['total']
        for row in queryset.values('status').annotate(total=Count('id'))
    }


def _status_section(queryset, **aliases):
    statuses = _status_counts(queryset)
    return {
        'total': sum(statuses.values()),
        'by_status': statuses,
        **{
            key: statuses.get(status, 0)
            for key, status in aliases.items()
        },
    }


def get_dashboard_metrics():
    users = _status_section(
        User.objects.all(),
        active='ACTIVE',
        locked='BLOCKED',
        pending_verification='PENDING_VERIFICATION',
    )
    sale_listings = SaleListing.objects.all()
    lend_listings = LendListing.objects.all()
    listing_statuses = _status_counts(sale_listings)
    for status_name, total in _status_counts(lend_listings).items():
        listing_statuses[status_name] = listing_statuses.get(status_name, 0) + total
    supported_listing_statuses = {
        value
        for model in (SaleListing, LendListing)
        for value, _label in model.STATUS_CHOICES
    }
    listings = {
        'total': sum(listing_statuses.values()),
        'by_status': listing_statuses,
        'active': listing_statuses.get('ACTIVE', 0),
        'sold': listing_statuses.get('SOLD', 0),
        'draft': listing_statuses.get('DRAFT', 0),
        'pending': listing_statuses.get('PENDING', 0),
        'rejected': listing_statuses.get('REJECTED', 0),
        'pending_status_supported': 'PENDING' in supported_listing_statuses,
        'rejected_status_supported': 'REJECTED' in supported_listing_statuses,
    }

    return {
        'users': users,
        'listings': listings,
        'lend_listings': _status_section(
            lend_listings,
            active='ACTIVE',
            on_loan='ON_LOAN',
        ),
        'reservations': _status_section(
            BookReservation.objects.all(),
            pending='PENDING',
            confirmed='CONFIRMED',
            completed='COMPLETED',
        ),
        'carts': _status_section(Cart.objects.all(), active='ACTIVE'),
        'orders': _status_section(
            Order.objects.all(),
            pending='PENDING_PAYMENT',
            completed='COMPLETED',
            cancelled='CANCELLED',
        ),
        'payments': _status_section(
            Payment.objects.all(),
            pending='PENDING',
            paid='PAID',
            failed='FAILED',
        ),
        'refunds': _status_section(
            Refund.objects.all(),
            requested='REQUESTED',
            completed='COMPLETED',
            rejected='REJECTED',
        ),
        'returns': _status_section(
            Return.objects.all(),
            requested='REQUESTED',
            approved='APPROVED',
            completed='COMPLETED',
        ),
        'shipments': _status_section(
            Shipment.objects.all(),
            pending='PENDING',
            shipped='SHIPPED',
            in_transit='IN_TRANSIT',
            delivered='DELIVERED',
        ),
        'reports': _status_section(
            Report.objects.all(),
            open='OPEN',
            in_review='IN_REVIEW',
            resolved='RESOLVED',
        ),
        'conversations': Conversation.objects.count(),
        'messages': Message.objects.count(),
        'favorites': Favorite.objects.count(),
    }
