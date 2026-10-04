import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from notifications.models import Notification
from books.models import (
    Book,
    BookEdition,
    BorrowOrder,
    BorrowTerms,
    Cart,
    Category,
    CheckoutGroup,
    LendListing,
    Order,
    Shipment,
    ShipmentTracking,
    BookWork,
)
from users.models import User


FIXTURE_PREFIX = 'borrow-return-acceptance-'
FIXTURE_PASSWORD = 'BorrowReturn-Acceptance-42!'
FIXTURE_EMAILS = {
    'lender': f'{FIXTURE_PREFIX}lender@example.invalid',
    'borrower': f'{FIXTURE_PREFIX}borrower@example.invalid',
    'outsider': f'{FIXTURE_PREFIX}outsider@example.invalid',
}


class Command(BaseCommand):
    help = 'Create, inspect, or clean isolated local Borrow Return browser fixtures.'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=('setup', 'verify', 'cleanup'),
        )
        parser.add_argument('--confirm-local-test-db', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm local test DB use.')
        self._assert_local_test_database()
        action = options['action']
        if action == 'setup':
            self._setup()
        elif action == 'verify':
            self._verify()
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
            raise CommandError('Set PASSBOOK_ENVIRONMENT=local or test for local fixture use.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), @@hostname, VERSION()')
            database_name, _server_hostname, _version = cursor.fetchone()
        if database_name != expected['NAME']:
            raise CommandError(
                f'Refusing fixture operation on unexpected SQL database {database_name}.',
            )

    def _setup(self):
        if User.objects.filter(email__in=FIXTURE_EMAILS.values()).exists():
            raise CommandError(
                'Acceptance fixture accounts already exist; inspect or cleanup them first.',
            )
        category = Category.objects.filter(name='Giáo trình', status='ACTIVE').first()
        if category is None:
            raise CommandError('The local DB needs an active Giáo trình category.')
        now = timezone.now()
        started_at = now - timedelta(days=1)
        with transaction.atomic():
            lender, borrower, _outsider = self._create_users(now)
            cart = Cart.objects.create(
                user=borrower,
                status='ACTIVE',
                created_at=now,
                updated_at=now,
            )
            fixture = {}
            for purpose, requester in (
                ('browser', borrower),
                ('concurrency', borrower),
            ):
                fixture[purpose] = self._create_active_borrow(
                    purpose=purpose,
                    lender=lender,
                    borrower=requester,
                    cart=cart,
                    category=category,
                    now=now,
                    started_at=started_at,
                )
        self.stdout.write(self.style.SUCCESS(json.dumps({
            'fixture_prefix': FIXTURE_PREFIX,
            'password': FIXTURE_PASSWORD,
            'users': {
                key: {'email': email, 'id': User.objects.get(email=email).id}
                for key, email in FIXTURE_EMAILS.items()
            },
            'borrows': {
                purpose: {
                    'borrow_id': borrow.id,
                    'order_id': borrow.order_id,
                    'book_id': borrow.lend_listing.book_id,
                    'listing_id': borrow.lend_listing_id,
                    'initial_shipment_id': shipment.id,
                }
                for purpose, (borrow, shipment) in fixture.items()
            },
        }, ensure_ascii=False)))

    @staticmethod
    def _create_users(now):
        users = {}
        for role, email in FIXTURE_EMAILS.items():
            users[role] = User.objects.create(
                email=email,
                password_hash=make_password(FIXTURE_PASSWORD),
                full_name=f'Return acceptance {role.title()}',
                role='STUDENT',
                status='ACTIVE',
                created_at=now,
                updated_at=now,
            )
        return users['lender'], users['borrower'], users['outsider']

    @staticmethod
    def _create_active_borrow(
        *,
        purpose,
        lender,
        borrower,
        cart,
        category,
        now,
        started_at,
    ):
        amount = Decimal('10000')
        checkout = CheckoutGroup.objects.create(
            checkout_code=f'{FIXTURE_PREFIX}{purpose}-checkout',
            idempotency_key=f'{FIXTURE_PREFIX}{purpose}-key',
            cart=cart,
            buyer=borrower,
            status='COMPLETED',
            currency='VND',
            subtotal=amount,
            shipping_total=Decimal('0'),
            discount_total=Decimal('0'),
            total_amount=amount,
            shipping_address_snapshot={'synthetic_acceptance_fixture': True},
            pricing_snapshot={'total_amount': str(amount), 'currency': 'VND'},
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        order = Order.objects.create(
            order_code=f'{FIXTURE_PREFIX}{purpose}-order',
            checkout_group=checkout,
            buyer=borrower,
            seller=lender,
            order_type='BORROW',
            status='CONFIRMED',
            currency='VND',
            subtotal=amount,
            shipping_fee=Decimal('0'),
            discount_amount=Decimal('0'),
            total_amount=amount,
            shipping_address_snapshot={'synthetic_acceptance_fixture': True},
            pricing_snapshot={'total_amount': str(amount), 'currency': 'VND'},
            placed_at=started_at,
            created_at=now,
            updated_at=now,
        )
        work = BookWork.objects.create(
            title=f'{FIXTURE_PREFIX}{purpose} book',
            description='Synthetic local return acceptance fixture.',
            author_name='Acceptance fixture',
            publisher_name='Acceptance fixture',
            category=category,
            created_by=lender,
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
        book = Book.objects.create(
            book_edition=edition,
            owner=lender,
            condition_label='LIKE_NEW',
            status='ON_LOAN',
            created_at=now,
            updated_at=now,
        )
        listing = LendListing.objects.create(
            book=book,
            lender=lender,
            title=work.title,
            description='Synthetic local return acceptance fixture.',
            status='ON_LOAN',
            deposit_amount=Decimal('0'),
            rental_fee=amount,
            currency='VND',
            published_at=started_at,
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
        borrow = BorrowOrder.objects.create(
            order=order,
            checkout_group=checkout,
            lend_listing=listing,
            lender=lender,
            borrower=borrower,
            status='ACTIVE',
            borrow_terms_snapshot={
                'max_days': 14,
                'deposit_required': False,
                'return_method': 'DELIVERY',
            },
            expected_start_at=started_at,
            expected_return_at=now + timedelta(days=13),
            actual_start_at=started_at,
            rental_fee=amount,
            deposit_amount=Decimal('0'),
            deposit_refunded_amount=Decimal('0'),
            deposit_forfeited_amount=Decimal('0'),
            late_fee_amount=Decimal('0'),
            currency='VND',
            created_at=now,
            updated_at=now,
        )
        shipment = Shipment.objects.create(
            order=order,
            carrier='Acceptance local carrier',
            tracking_code=f'{FIXTURE_PREFIX}{purpose}-outbound',
            shipping_fee=Decimal('0'),
            status='DELIVERED',
            shipped_at=started_at,
            delivered_at=started_at + timedelta(hours=2),
            currency='VND',
            created_at=now,
            updated_at=now,
        )
        ShipmentTracking.objects.create(
            shipment=shipment,
            status='DELIVERED',
            source='SYSTEM',
            location='Local acceptance fixture',
            description='Initial OWNER_TO_BORROWER shipment delivered.',
            occurred_at=shipment.delivered_at,
            created_at=now,
        )
        return borrow, shipment

    def _verify(self):
        borrows = list(
            BorrowOrder.objects.filter(
                order__order_code__startswith=FIXTURE_PREFIX,
            ).select_related('lend_listing__book', 'order').order_by('id'),
        )
        if len(borrows) != 2:
            raise CommandError(f'Expected exactly 2 acceptance borrows, found {len(borrows)}.')
        for borrow in borrows:
            if (
                borrow.status != 'ACTIVE'
                or borrow.lend_listing.status != 'ON_LOAN'
                or borrow.lend_listing.book.status != 'ON_LOAN'
                or not borrow.order.shipments.filter(status='DELIVERED').exists()
            ):
                raise CommandError(
                    f'Fixture Borrow #{borrow.id} is not ACTIVE with outbound delivery.',
                )
        self.stdout.write(self.style.SUCCESS(
            'Fixture verified: 2 ACTIVE borrows, ON_LOAN books/listings, initial delivered shipments.',
        ))

    def _cleanup(self):
        borrow_ids = list(
            BorrowOrder.objects.filter(
                order__order_code__startswith=FIXTURE_PREFIX,
            ).values_list('id', flat=True),
        )
        order_ids = list(
            Order.objects.filter(order_code__startswith=FIXTURE_PREFIX).values_list(
                'id',
                flat=True,
            ),
        )
        shipment_ids = list(
            Shipment.objects.filter(
                order_id__in=order_ids,
            ).values_list('id', flat=True),
        )
        listing_ids = list(
            LendListing.objects.filter(
                title__startswith=FIXTURE_PREFIX,
            ).values_list('id', flat=True),
        )
        book_ids = list(
            Book.objects.filter(
                book_edition__book_work__title__startswith=FIXTURE_PREFIX,
            ).values_list('id', flat=True),
        )
        work_ids = list(
            BookWork.objects.filter(title__startswith=FIXTURE_PREFIX).values_list(
                'id',
                flat=True,
            ),
        )
        checkout_ids = list(
            CheckoutGroup.objects.filter(
                checkout_code__startswith=FIXTURE_PREFIX,
            ).values_list('id', flat=True),
        )
        cart_ids = list(
            Cart.objects.filter(
                user__email__in=FIXTURE_EMAILS.values(),
            ).values_list('id', flat=True),
        )
        user_ids = list(
            User.objects.filter(email__in=FIXTURE_EMAILS.values()).values_list(
                'id',
                flat=True,
            ),
        )
        with transaction.atomic():
            ShipmentTracking.objects.filter(shipment_id__in=shipment_ids).delete()
            Shipment.objects.filter(pk__in=shipment_ids).delete()
            BorrowOrder.objects.filter(pk__in=borrow_ids).delete()
            Order.objects.filter(pk__in=order_ids).delete()
            CheckoutGroup.objects.filter(pk__in=checkout_ids).delete()
            Cart.objects.filter(pk__in=cart_ids).delete()
            BorrowTerms.objects.filter(lend_listing_id__in=listing_ids).delete()
            LendListing.objects.filter(pk__in=listing_ids).delete()
            Book.objects.filter(pk__in=book_ids).delete()
            BookEdition.objects.filter(book_work_id__in=work_ids).delete()
            BookWork.objects.filter(pk__in=work_ids).delete()
            Notification.objects.filter(user_id__in=user_ids).delete()
            User.objects.filter(email__in=FIXTURE_EMAILS.values()).delete()
        self.stdout.write(self.style.SUCCESS(
            f'Cleaned acceptance fixture only: borrows={len(borrow_ids)}, '
            f'shipments={len(shipment_ids)}, books={len(book_ids)}, '
            f'users={len(FIXTURE_EMAILS)}.',
        ))
