from decimal import Decimal

from django.db import models

from users.models import Language, Subject, User


class Category(models.Model):
    parent = models.ForeignKey(
        'self', db_column='parent_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='children',
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'categories'


class BookWork(models.Model):
    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    author_name = models.CharField(max_length=500, null=True, blank=True)
    publisher_name = models.CharField(max_length=255, null=True, blank=True)
    category = models.ForeignKey(
        Category, db_column='category_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='book_works',
    )
    created_by = models.ForeignKey(
        User, db_column='created_by', on_delete=models.DO_NOTHING,
        related_name='created_book_works',
    )
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_works'


class BookWorkSubject(models.Model):
    # Django 4.2 cannot declare the schema's composite primary key directly.
    book_work = models.ForeignKey(
        BookWork, db_column='book_work_id', primary_key=True,
        on_delete=models.DO_NOTHING, related_name='subject_links',
    )
    subject = models.ForeignKey(
        Subject, db_column='subject_id', on_delete=models.DO_NOTHING,
        related_name='work_links',
    )
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_work_subjects'
        unique_together = [('book_work', 'subject')]


class BookEdition(models.Model):
    book_work = models.ForeignKey(
        BookWork, db_column='book_work_id', on_delete=models.DO_NOTHING,
        related_name='editions',
    )
    edition_name = models.CharField(max_length=100, null=True, blank=True)
    edition_number = models.PositiveSmallIntegerField(null=True, blank=True)
    publisher_name = models.CharField(max_length=255, null=True, blank=True)
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    format = models.CharField(max_length=30, null=True, blank=True)
    language = models.ForeignKey(
        Language, db_column='language_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='book_editions',
    )
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_editions'


class BookIdentifier(models.Model):
    book_edition = models.ForeignKey(
        BookEdition, db_column='book_edition_id', on_delete=models.DO_NOTHING,
        related_name='identifiers',
    )
    identifier_type = models.CharField(max_length=30)
    identifier_value = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_identifiers'
        unique_together = [('identifier_type', 'identifier_value')]


class Book(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'), ('RESERVED', 'Reserved'),
        ('ON_LOAN', 'On loan'), ('SOLD', 'Sold'), ('UNAVAILABLE', 'Unavailable'),
    ]
    CONDITION_CHOICES = [
        ('new', 'New'), ('like_new', 'Like new'), ('good', 'Good'), ('used', 'Used'),
    ]

    book_edition = models.ForeignKey(
        BookEdition, db_column='book_edition_id', on_delete=models.DO_NOTHING,
        related_name='physical_books',
    )
    owner = models.ForeignKey(
        User, db_column='owner_id', on_delete=models.DO_NOTHING,
        related_name='books',
    )
    condition_label = models.CharField(max_length=30)
    condition_description = models.TextField(null=True, blank=True)
    acquisition_type = models.CharField(max_length=30, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    @property
    def seller(self):
        return self.owner

    @property
    def seller_id(self):
        return self.owner_id

    def _active_sale_listing(self):
        active_listings = getattr(self, 'active_sale_listings', None)
        if active_listings is not None:
            return next(
                (
                    item for item in active_listings
                    if item.status in ('ACTIVE', 'RESERVED')
                ),
                active_listings[0] if active_listings else None,
            )
        listings = getattr(self, '_prefetched_objects_cache', {}).get('sale_listings')
        if listings is not None:
            return next((item for item in listings if item.status in ('ACTIVE', 'RESERVED')), None)
        return self.sale_listings.filter(status__in=('ACTIVE', 'RESERVED')).first()

    def _active_lend_listing(self):
        active_listings = getattr(self, 'active_lend_listings', None)
        if active_listings is not None:
            return next(
                (
                    item for item in active_listings
                    if item.status in ('ACTIVE', 'RESERVED', 'ON_LOAN')
                ),
                active_listings[0] if active_listings else None,
            )
        listings = getattr(self, '_prefetched_objects_cache', {}).get('lend_listings')
        if listings is not None:
            return next(
                (
                    item for item in listings
                    if item.status in ('ACTIVE', 'RESERVED', 'ON_LOAN')
                ),
                None,
            )
        return self.lend_listings.filter(
            status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
        ).first()

    @property
    def title(self):
        listing = self._active_sale_listing() or self._active_lend_listing()
        return listing.title if listing else self.book_edition.book_work.title

    @property
    def description(self):
        listing = self._active_sale_listing() or self._active_lend_listing()
        return listing.description if listing else self.book_edition.book_work.description

    @property
    def price(self):
        sale_listing = self._active_sale_listing()
        if sale_listing is not None:
            return sale_listing.price
        lend_listing = self._active_lend_listing()
        return lend_listing.rental_fee if lend_listing else Decimal('0')

    @property
    def condition_status(self):
        value = self.condition_label.lower().replace(' ', '_')
        return value if value in {choice for choice, _ in self.CONDITION_CHOICES} else 'used'

    @property
    def subject(self):
        work = self.book_edition.book_work
        links = getattr(work, 'primary_subject_links', None)
        if links is None:
            links = getattr(work, '_prefetched_objects_cache', {}).get('subject_links')
        if links is not None:
            primary = next((link for link in links if link.is_primary), None)
            return primary.subject if primary else None
        link = (
            self.book_edition.book_work.subject_links
            .select_related('subject')
            .filter(is_primary=True)
            .first()
        )
        return link.subject if link else None

    @property
    def category(self):
        return self.book_edition.book_work.category

    @property
    def edition(self):
        return self.book_edition.edition_name

    @property
    def publication_year(self):
        return self.book_edition.publication_year

    @property
    def pickup_location(self):
        return None

    @property
    def pickup_location_id(self):
        return None

    class Meta:
        managed = False
        db_table = 'books'


class BookImage(models.Model):
    book = models.ForeignKey(
        Book, db_column='book_id', on_delete=models.DO_NOTHING,
        related_name='images',
    )
    image_url = models.URLField(max_length=2048)
    cloudinary_public_id = models.CharField(max_length=255, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_images'


class SaleListing(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('PENDING', 'Pending review'),
        ('ACTIVE', 'Active'), ('REJECTED', 'Rejected'),
        ('RESERVED', 'Reserved'), ('SOLD', 'Sold'),
        ('CLOSED', 'Closed'), ('EXPIRED', 'Expired'),
    ]
    book = models.ForeignKey(
        Book, db_column='book_id', on_delete=models.DO_NOTHING,
        related_name='sale_listings',
    )
    seller = models.ForeignKey(
        User, db_column='seller_id', on_delete=models.DO_NOTHING,
        related_name='sale_listings',
    )
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='VND')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'sale_listings'


class LendListing(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('ACTIVE', 'Active'), ('RESERVED', 'Reserved'),
        ('ON_LOAN', 'On loan'), ('CLOSED', 'Closed'), ('EXPIRED', 'Expired'),
    ]
    book = models.ForeignKey(
        Book, db_column='book_id', on_delete=models.DO_NOTHING,
        related_name='lend_listings',
    )
    lender = models.ForeignKey(
        User, db_column='lender_id', on_delete=models.DO_NOTHING,
        related_name='lend_listings',
    )
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    deposit_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    rental_fee = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='VND')
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'lend_listings'


class BorrowTerms(models.Model):
    lend_listing = models.OneToOneField(
        LendListing, db_column='lend_listing_id', on_delete=models.DO_NOTHING,
        related_name='borrow_terms',
    )
    max_days = models.PositiveSmallIntegerField()
    late_fee_per_day = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    deposit_required = models.BooleanField(default=False)
    shipping_paid_by = models.CharField(max_length=20)
    return_method = models.CharField(max_length=30)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'borrow_terms'


class BookRequest(models.Model):
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING, related_name='book_requests')
    request_type = models.CharField(max_length=20)
    book_work = models.ForeignKey(
        BookWork, db_column='book_work_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='requests',
    )
    category = models.ForeignKey(
        Category, db_column='category_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='requests',
    )
    title_keyword = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    budget_max = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    asking_price = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    currency = models.CharField(max_length=3, null=True, blank=True)
    condition_preference = models.CharField(max_length=30, null=True, blank=True)
    status = models.CharField(max_length=20, default='OPEN')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_requests'


class RequestInterest(models.Model):
    request = models.ForeignKey(BookRequest, db_column='request_id', on_delete=models.DO_NOTHING, related_name='interests')
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING, related_name='request_interests')
    note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'request_interests'
        unique_together = [('request', 'user')]


class RequestMatch(models.Model):
    request = models.ForeignKey(BookRequest, db_column='request_id', on_delete=models.DO_NOTHING, related_name='matches')
    matched_request = models.ForeignKey(
        BookRequest, db_column='matched_request_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='matches_for_request',
    )
    sale_listing = models.ForeignKey(
        SaleListing, db_column='sale_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='request_matches',
    )
    lend_listing = models.ForeignKey(
        LendListing, db_column='lend_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='request_matches',
    )
    match_type = models.CharField(max_length=20)
    score = models.DecimalField(max_digits=6, decimal_places=5, null=True, blank=True)
    status = models.CharField(max_length=20, default='SUGGESTED')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'request_matches'


class Cart(models.Model):
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING, related_name='carts')
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'carts'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, db_column='cart_id', on_delete=models.DO_NOTHING, related_name='items')
    sale_listing = models.ForeignKey(
        SaleListing, db_column='sale_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='cart_items',
    )
    lend_listing = models.ForeignKey(
        LendListing, db_column='lend_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='cart_items',
    )
    unit_price = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='VND')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'cart_items'


class CheckoutGroup(models.Model):
    checkout_code = models.CharField(max_length=64, unique=True)
    idempotency_key = models.CharField(max_length=128)
    cart = models.ForeignKey(Cart, db_column='cart_id', on_delete=models.DO_NOTHING, related_name='checkouts')
    buyer = models.ForeignKey(User, db_column='buyer_id', on_delete=models.DO_NOTHING, related_name='checkouts')
    status = models.CharField(max_length=20)
    currency = models.CharField(max_length=3, default='VND')
    subtotal = models.DecimalField(max_digits=19, decimal_places=4)
    shipping_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    discount_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=19, decimal_places=4)
    shipping_address_snapshot = models.JSONField()
    pricing_snapshot = models.JSONField()
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'checkout_groups'
        unique_together = [('buyer', 'idempotency_key')]


class Order(models.Model):
    order_code = models.CharField(max_length=64, unique=True)
    checkout_group = models.ForeignKey(CheckoutGroup, db_column='checkout_group_id', on_delete=models.DO_NOTHING, related_name='orders')
    buyer = models.ForeignKey(User, db_column='buyer_id', on_delete=models.DO_NOTHING, related_name='buyer_orders')
    seller = models.ForeignKey(User, db_column='seller_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='seller_orders')
    order_type = models.CharField(max_length=20)
    status = models.CharField(max_length=30, default='PENDING_PAYMENT')
    currency = models.CharField(max_length=3, default='VND')
    subtotal = models.DecimalField(max_digits=19, decimal_places=4)
    shipping_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=19, decimal_places=4)
    shipping_address_snapshot = models.JSONField()
    pricing_snapshot = models.JSONField()
    note = models.TextField(null=True, blank=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'orders'


class SaleOrderItem(models.Model):
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='sale_items')
    sale_listing = models.ForeignKey(SaleListing, db_column='sale_listing_id', on_delete=models.DO_NOTHING, related_name='sale_order_items')
    book = models.ForeignKey(Book, db_column='book_id', on_delete=models.DO_NOTHING, related_name='sale_order_items')
    seller = models.ForeignKey(User, db_column='seller_id', on_delete=models.DO_NOTHING, related_name='sale_order_items')
    title_snapshot = models.CharField(max_length=500)
    condition_snapshot = models.CharField(max_length=30)
    unit_price = models.DecimalField(max_digits=19, decimal_places=4)
    discount_allocated = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    quantity = models.PositiveSmallIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=19, decimal_places=4)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'sale_order_items'
        unique_together = [('order', 'sale_listing')]


class BorrowOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed'), ('REJECTED', 'Rejected'),
        ('READY_FOR_PICKUP', 'Ready for pickup'), ('ACTIVE', 'Active'),
        ('RETURN_REQUESTED', 'Return requested'), ('RETURNED', 'Returned'),
        ('CANCELLED', 'Cancelled'), ('OVERDUE', 'Overdue'), ('DISPUTED', 'Disputed'),
        ('COMPLETED', 'Completed'),
    ]
    order = models.OneToOneField(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='borrow_order')
    checkout_group = models.ForeignKey(CheckoutGroup, db_column='checkout_group_id', on_delete=models.DO_NOTHING, related_name='borrow_orders')
    lend_listing = models.ForeignKey(LendListing, db_column='lend_listing_id', on_delete=models.DO_NOTHING, related_name='borrow_orders')
    lender = models.ForeignKey(User, db_column='lender_id', on_delete=models.DO_NOTHING, related_name='lending_orders')
    borrower = models.ForeignKey(User, db_column='borrower_id', on_delete=models.DO_NOTHING, related_name='borrowing_orders')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    borrow_terms_snapshot = models.JSONField()
    expected_start_at = models.DateTimeField(null=True, blank=True)
    expected_return_at = models.DateTimeField(null=True, blank=True)
    actual_start_at = models.DateTimeField(null=True, blank=True)
    actual_return_at = models.DateTimeField(null=True, blank=True)
    rental_fee = models.DecimalField(max_digits=19, decimal_places=4)
    deposit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    deposit_refunded_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    deposit_forfeited_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    late_fee_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    return_requested_by = models.ForeignKey(
        User, db_column='return_requested_by', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='return_requests',
    )
    return_status = models.CharField(max_length=20, null=True, blank=True)
    return_method = models.CharField(max_length=30, null=True, blank=True)
    return_tracking_code = models.CharField(max_length=100, null=True, blank=True)
    return_requested_at = models.DateTimeField(null=True, blank=True)
    return_approved_at = models.DateTimeField(null=True, blank=True)
    return_notes = models.TextField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='VND')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'borrow_orders'


class Payment(models.Model):
    checkout_group = models.ForeignKey(CheckoutGroup, db_column='checkout_group_id', on_delete=models.DO_NOTHING, related_name='payments')
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='payments')
    payer = models.ForeignKey(User, db_column='payer_id', on_delete=models.DO_NOTHING, related_name='payments')
    provider = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=30)
    provider_transaction_code = models.CharField(max_length=150, null=True, blank=True)
    payment_purpose = models.CharField(max_length=30, default='CHECKOUT')
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    platform_fee_rate = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    platform_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    seller_amount = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='VND')
    status = models.CharField(max_length=20, default='PENDING')
    idempotency_key = models.CharField(max_length=128)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'payments'
        unique_together = [('provider', 'idempotency_key')]


class Shipment(models.Model):
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='shipments')
    carrier = models.CharField(max_length=100, null=True, blank=True)
    tracking_code = models.CharField(max_length=150, null=True, blank=True)
    shipping_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='VND')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'shipments'


class ShipmentTracking(models.Model):
    shipment = models.ForeignKey(Shipment, db_column='shipment_id', on_delete=models.DO_NOTHING, related_name='tracking_events')
    status = models.CharField(max_length=30)
    location = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'shipment_tracking'


class Return(models.Model):
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='returns')
    sale_order_item = models.ForeignKey(SaleOrderItem, db_column='sale_order_item_id', on_delete=models.DO_NOTHING, related_name='returns')
    reason = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='REQUESTED')
    requested_by = models.ForeignKey(User, db_column='requested_by', on_delete=models.DO_NOTHING, related_name='returns')
    requested_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'returns'


class Refund(models.Model):
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='refunds')
    payment = models.ForeignKey(Payment, db_column='payment_id', on_delete=models.DO_NOTHING, related_name='refunds')
    sale_order_item = models.ForeignKey(SaleOrderItem, db_column='sale_order_item_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='refunds')
    borrow_order = models.ForeignKey(BorrowOrder, db_column='borrow_order_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='refunds')
    return_record = models.ForeignKey(Return, db_column='return_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='refunds')
    requested_by = models.ForeignKey(User, db_column='requested_by', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='requested_refunds')
    provider = models.CharField(max_length=50)
    provider_refund_reference = models.CharField(max_length=150, null=True, blank=True)
    idempotency_key = models.CharField(max_length=128)
    reason = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='VND')
    status = models.CharField(max_length=20, default='REQUESTED')
    requested_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'refunds'
        unique_together = [('provider', 'idempotency_key')]


class Favorite(models.Model):
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING, related_name='favorites')
    book = models.ForeignKey(Book, db_column='book_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='favorites')
    sale_listing = models.ForeignKey(SaleListing, db_column='sale_listing_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='favorites')
    lend_listing = models.ForeignKey(LendListing, db_column='lend_listing_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='favorites')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'favorites'


class BookReservation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed'), ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'), ('EXPIRED', 'Expired'), ('COMPLETED', 'Completed'),
    ]
    book = models.ForeignKey(Book, db_column='book_id', on_delete=models.DO_NOTHING, related_name='reservations')
    requester = models.ForeignKey(User, db_column='requester_id', on_delete=models.DO_NOTHING, related_name='book_reservations')
    owner = models.ForeignKey(User, db_column='owner_id', on_delete=models.DO_NOTHING, related_name='owned_book_reservations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_reservations'


class Review(models.Model):
    reviewer = models.ForeignKey(User, db_column='reviewer_id', on_delete=models.DO_NOTHING, related_name='reviews')
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING, related_name='reviews')
    sale_listing = models.ForeignKey(SaleListing, db_column='sale_listing_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='reviews')
    lend_listing = models.ForeignKey(LendListing, db_column='lend_listing_id', null=True, blank=True, on_delete=models.DO_NOTHING, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'reviews'
        unique_together = [('order', 'reviewer')]
