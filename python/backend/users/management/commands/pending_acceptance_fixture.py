from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from books.models import (
    Book,
    BookEdition,
    BookReservation,
    BookWork,
    BorrowOrder,
    BorrowTerms,
    Cart,
    Category,
    CheckoutGroup,
    LendListing,
    Order,
    Payment,
    Return,
    Shipment,
    ShipmentTracking,
)
from notifications.models import Notification
from users.models import User


FIXTURE_PREFIX = 'pending-acceptance-'
FIXTURE_PASSWORD = 'AcceptanceOnly-Pending-42!'
FIXTURE_EMAILS = {
    'customer': 'acceptance.customer@example.com',
    'other_customer': 'acceptance.other@example.com',
    'owner': 'acceptance.owner@example.com',
    'admin': 'acceptance.admin@example.com',
}
FIXTURE_USER_DETAILS = {
    'acceptance.customer@example.com': ('Acceptance Customer', 'STUDENT'),
    'acceptance.other@example.com': ('Acceptance Other Customer', 'STUDENT'),
    'acceptance.owner@example.com': ('Acceptance Listing Owner', 'STUDENT'),
    'acceptance.admin@example.com': ('Acceptance Admin', 'ADMIN'),
}


class Command(BaseCommand):
    help = 'Create or clean isolated local Pending Reservation/Borrow acceptance fixtures.'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=('setup', 'cleanup'))
        parser.add_argument('--confirm-local-test-db', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm local test DB use.')
        self._assert_local_test_database()
        if options['action'] == 'setup':
            self._setup()
        else:
            self._cleanup()

    @staticmethod
    def _assert_local_test_database():
        database = settings.DATABASES['default']
        expected = {
            'NAME': 'passbook_v12_lite_test',
            'HOST': '127.0.0.1',
            'PORT': '3308',
            'USER': 'root',
        }
        if any(str(database.get(key, '')) != value for key, value in expected.items()):
            raise CommandError(
                'Refusing fixture operation outside 127.0.0.1:3308/passbook_v12_lite_test.',
            )
        if settings.PASSBOOK_ENVIRONMENT not in ('local', 'test'):
            raise CommandError('Set PASSBOOK_ENVIRONMENT=local or test for fixture use.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            database_name = cursor.fetchone()[0]
        if database_name != expected['NAME']:
            raise CommandError(
                f'Refusing fixture operation on unexpected SQL database {database_name}.',
            )

    def _setup(self):
        if User.objects.filter(email__in=FIXTURE_EMAILS.values()).exists():
            raise CommandError(
                'Acceptance fixture accounts already exist; inspect or cleanup them first.',
            )
        if User.objects.filter(email=FIXTURE_EMAILS['admin']).exists():
            raise CommandError('The requested acceptance admin email is already in use.')
        category = Category.objects.filter(name='Giáo trình', status='ACTIVE').first()
        if category is None:
            raise CommandError('The local DB needs an active Giáo trình category.')

        now = timezone.now()
        with transaction.atomic():
            users = {
                'customer': self._create_user(
                    FIXTURE_EMAILS['customer'],
                    'Acceptance Customer',
                    'STUDENT',
                    now,
                ),
                'other_customer': self._create_user(
                    FIXTURE_EMAILS['other_customer'],
                    'Acceptance Other Customer',
                    'STUDENT',
                    now,
                ),
                'owner': self._create_user(
                    FIXTURE_EMAILS['owner'],
                    'Acceptance Listing Owner',
                    'STUDENT',
                    now,
                ),
                'admin': self._create_user(
                    FIXTURE_EMAILS['admin'],
                    'Acceptance Admin',
                    'ADMIN',
                    now,
                ),
            }

            listings = {}
            for purpose in (
                'reservation',
                'concurrency',
                'borrow',
                'other-borrow',
            ):
                listings[purpose] = self._create_listing(
                    purpose=purpose,
                    owner=users['owner'],
                    category=category,
                    now=now,
                )
            self._create_pending_borrow(
                purpose='borrow',
                listing=listings['borrow'],
                borrower=users['customer'],
                now=now,
            )
            self._create_pending_borrow(
                purpose='other-borrow',
                listing=listings['other-borrow'],
                borrower=users['other_customer'],
                now=now,
            )

        self.stdout.write(self.style.SUCCESS(
            'Pending acceptance fixtures ready. '
            f'Customer={users["customer"].id}, Admin={users["admin"].id}, '
            f'Owner={users["owner"].id}; '
            + ', '.join(
                f'{purpose} book={listing.book_id}/listing={listing.id}'
                for purpose, listing in listings.items()
            )
            + '; BorrowOrder records were created as synthetic coherent fixtures '
            '(no BorrowOrder create API exists); Reservation must be created through API.'
        ))

    @staticmethod
    def _create_user(email, full_name, role, now):
        return User.objects.create(
            email=email,
            password_hash=make_password(FIXTURE_PASSWORD),
            full_name=full_name,
            role=role,
            status='ACTIVE',
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _create_listing(*, purpose, owner, category, now):
        title = f'{FIXTURE_PREFIX}{purpose}'
        work = BookWork.objects.create(
            title=title,
            description='Synthetic local Pending acceptance fixture.',
            author_name='Acceptance fixture',
            publisher_name='Acceptance fixture',
            category=category,
            created_by=owner,
            status='ACTIVE',
            created_at=now,
            updated_at=now,
        )
        edition = BookEdition.objects.create(
            book_work=work,
            edition_name='Acceptance edition',
            edition_number=1,
            publisher_name='Acceptance fixture',
            publication_year=2026,
            created_at=now,
            updated_at=now,
        )
        reserved = purpose in ('borrow', 'other-borrow')
        book = Book.objects.create(
            book_edition=edition,
            owner=owner,
            condition_label='LIKE_NEW',
            status='RESERVED' if reserved else 'AVAILABLE',
            created_at=now,
            updated_at=now,
        )
        listing = LendListing.objects.create(
            book=book,
            lender=owner,
            title=title,
            description='Synthetic local Pending acceptance fixture.',
            status='RESERVED' if reserved else 'ACTIVE',
            deposit_amount=Decimal('0'),
            rental_fee=Decimal('10000'),
            currency='VND',
            published_at=now,
            created_at=now,
            updated_at=now,
        )
        BorrowTerms.objects.create(
            lend_listing=listing,
            max_days=14,
            deposit_required=False,
            shipping_paid_by='BORROWER',
            return_method='DELIVERY',
            notes='Synthetic local acceptance terms.',
            created_at=now,
            updated_at=now,
        )
        return listing

    @staticmethod
    def _create_pending_borrow(*, purpose, listing, borrower, now):
        cart = Cart.objects.create(
            user=borrower,
            status='ACTIVE',
            created_at=now,
            updated_at=now,
        )
        amount = Decimal('10000')
        checkout = CheckoutGroup.objects.create(
            checkout_code=f'{FIXTURE_PREFIX}{purpose}-checkout',
            idempotency_key=f'{FIXTURE_PREFIX}{purpose}-key',
            cart=cart,
            buyer=borrower,
            status='PENDING',
            currency='VND',
            subtotal=amount,
            shipping_total=Decimal('0'),
            discount_total=Decimal('0'),
            total_amount=amount,
            shipping_address_snapshot={'synthetic_acceptance_fixture': True},
            pricing_snapshot={'total_amount': str(amount), 'currency': 'VND'},
            created_at=now,
            updated_at=now,
        )
        order = Order.objects.create(
            order_code=f'{FIXTURE_PREFIX}{purpose}-order',
            checkout_group=checkout,
            buyer=borrower,
            seller=listing.lender,
            order_type='BORROW',
            status='PENDING_PAYMENT',
            currency='VND',
            subtotal=amount,
            shipping_fee=Decimal('0'),
            discount_amount=Decimal('0'),
            total_amount=amount,
            shipping_address_snapshot={'synthetic_acceptance_fixture': True},
            pricing_snapshot={'total_amount': str(amount), 'currency': 'VND'},
            placed_at=now,
            created_at=now,
            updated_at=now,
        )
        BorrowOrder.objects.create(
            order=order,
            checkout_group=checkout,
            lend_listing=listing,
            lender=listing.lender,
            borrower=borrower,
            status='PENDING',
            borrow_terms_snapshot={
                'max_days': 14,
                'deposit_required': False,
                'return_method': 'DELIVERY',
            },
            expected_start_at=now + timedelta(days=1),
            expected_return_at=now + timedelta(days=15),
            rental_fee=amount,
            deposit_amount=Decimal('0'),
            deposit_refunded_amount=Decimal('0'),
            deposit_forfeited_amount=Decimal('0'),
            late_fee_amount=Decimal('0'),
            currency='VND',
            created_at=now,
            updated_at=now,
        )

    def _cleanup(self):
        fixture_users = list(User.objects.filter(email__in=FIXTURE_EMAILS.values()))
        unexpected_users = [
            user.email
            for user in fixture_users
            if (user.full_name, user.role) != FIXTURE_USER_DETAILS[user.email]
        ]
        if unexpected_users:
            raise CommandError(
                'Refusing to delete accounts that do not match this fixture: '
                + ', '.join(unexpected_users),
            )
        user_ids = [user.id for user in fixture_users]
        books = list(Book.objects.filter(
            book_edition__book_work__title__startswith=FIXTURE_PREFIX,
        ))
        book_ids = [book.id for book in books]
        listings = list(LendListing.objects.filter(
            title__startswith=FIXTURE_PREFIX,
        ))
        listing_ids = [listing.id for listing in listings]
        borrows = list(BorrowOrder.objects.filter(
            order__order_code__startswith=FIXTURE_PREFIX,
        ))
        borrow_ids = [borrow.id for borrow in borrows]
        orders = list(Order.objects.filter(
            order_code__startswith=FIXTURE_PREFIX,
        ))
        order_ids = [order.id for order in orders]
        checkouts = list(CheckoutGroup.objects.filter(
            checkout_code__startswith=FIXTURE_PREFIX,
        ))
        checkout_ids = [checkout.id for checkout in checkouts]
        carts = list(Cart.objects.filter(user_id__in=user_ids))
        cart_ids = [cart.id for cart in carts]

        with transaction.atomic():
            Notification.objects.filter(user_id__in=user_ids).delete()
            BookReservation.objects.filter(
                Q(requester_id__in=user_ids)
                | Q(owner_id__in=user_ids)
                | Q(book_id__in=book_ids),
            ).delete()
            Payment.objects.filter(order_id__in=order_ids).delete()
            ShipmentTracking.objects.filter(shipment__order_id__in=order_ids).delete()
            Shipment.objects.filter(order_id__in=order_ids).delete()
            Return.objects.filter(order_id__in=order_ids).delete()
            BorrowOrder.objects.filter(pk__in=borrow_ids).delete()
            Order.objects.filter(pk__in=order_ids).delete()
            CheckoutGroup.objects.filter(pk__in=checkout_ids).delete()
            Cart.objects.filter(pk__in=cart_ids).delete()
            BorrowTerms.objects.filter(lend_listing_id__in=listing_ids).delete()
            LendListing.objects.filter(pk__in=listing_ids).delete()
            Book.objects.filter(pk__in=book_ids).delete()
            BookEdition.objects.filter(
                book_work__title__startswith=FIXTURE_PREFIX,
            ).delete()
            BookWork.objects.filter(title__startswith=FIXTURE_PREFIX).delete()
            User.objects.filter(pk__in=user_ids).delete()

        remaining = {
            'users': User.objects.filter(email__in=FIXTURE_EMAILS.values()).count(),
            'reservations': BookReservation.objects.filter(book_id__in=book_ids).count(),
            'borrow_orders': BorrowOrder.objects.filter(pk__in=borrow_ids).count(),
            'orders': Order.objects.filter(pk__in=order_ids).count(),
            'listings': LendListing.objects.filter(pk__in=listing_ids).count(),
            'books': Book.objects.filter(pk__in=book_ids).count(),
        }
        if any(remaining.values()):
            raise CommandError(f'Fixture cleanup incomplete: {remaining}')
        self.stdout.write(self.style.SUCCESS(f'Acceptance fixtures cleaned: {remaining}'))
