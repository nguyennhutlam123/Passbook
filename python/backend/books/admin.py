from django.contrib import admin
from django.contrib import messages
from django.utils import timezone

from config.composite_admin import CompositeKeyAdmin

from .models import (
    Book,
    BookEdition,
    BookIdentifier,
    BookImage,
    BookRequest,
    BookReservation,
    BookWork,
    BookWorkSubject,
    BorrowTerms,
    BorrowOrder,
    Category,
    Cart,
    CartItem,
    CheckoutGroup,
    Favorite,
    LendListing,
    Order,
    Payment,
    Refund,
    Review,
    RequestInterest,
    RequestMatch,
    Return,
    SaleListing,
    SaleOrderItem,
    Shipment,
    ShipmentTracking,
)

admin.site.register((
    Category,
    BookWork,
    BookEdition,
    BookIdentifier,
    Book,
    BookImage,
    LendListing,
    BorrowTerms,
    BookRequest,
    RequestInterest,
    RequestMatch,
    BookReservation,
    Cart,
    CartItem,
    CheckoutGroup,
    Order,
    SaleOrderItem,
    BorrowOrder,
    Payment,
    Shipment,
    ShipmentTracking,
    Return,
    Refund,
    Review,
    Favorite,
))


@admin.register(SaleListing)
class SaleListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'seller', 'price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description', 'seller__email', 'seller__full_name')
    actions = ('approve_pending', 'reject_pending')

    @admin.action(description='Approve selected pending listings')
    def approve_pending(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status='PENDING').update(
            status='ACTIVE',
            published_at=now,
            updated_at=now,
        )
        self._report_moderation_result(request, updated, 'approved')

    @admin.action(description='Reject selected pending listings')
    def reject_pending(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='REJECTED',
            updated_at=timezone.now(),
        )
        self._report_moderation_result(request, updated, 'rejected')

    def _report_moderation_result(self, request, updated, action):
        if updated:
            self.message_user(
                request,
                f'{updated} listing(s) {action}.',
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                'No pending listings were changed.',
                level=messages.WARNING,
            )


@admin.register(BookWorkSubject)
class BookWorkSubjectAdmin(CompositeKeyAdmin):
    composite_key_fields = ('book_work', 'subject')
    list_display = (
        'composite_key_link',
        'book_work_id',
        'subject_id',
        'is_primary',
        'created_at',
        'composite_delete_link',
    )
    list_filter = ('is_primary',)
    ordering = ('book_work_id', 'subject_id')
