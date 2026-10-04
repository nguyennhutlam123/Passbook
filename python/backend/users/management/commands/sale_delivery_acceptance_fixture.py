from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from books.models import (
    Book,
    BookEdition,
    BookWork,
    Cart,
    CartItem,
    Category,
    CheckoutGroup,
    Order,
    Payment,
    Refund,
    Return,
    Review,
    SaleListing,
    SaleOrderItem,
    Shipment,
    ShipmentTracking,
)
from notifications.models import Notification
from users.models import User


FIXTURE_PREFIX = 'sale-delivery-acceptance-'
FIXTURE_PASSWORD = 'SaleDelivery-LocalOnly-73!'
FIXTURE_USERS = {
    'customer': ('sale.acceptance.customer@example.com', 'SALE Acceptance Customer', 'STUDENT'),
    'seller': ('sale.acceptance.seller@example.com', 'SALE Acceptance Seller', 'STUDENT'),
    'admin': ('sale.acceptance.admin@example.com', 'SALE Acceptance Admin', 'ADMIN'),
}


class Command(BaseCommand):
    help = 'Create or clean a local SALE order delivery acceptance fixture.'

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
        emails = [email for email, _name, _role in FIXTURE_USERS.values()]
        if User.objects.filter(email__in=emails).exists():
            raise CommandError('A SALE delivery acceptance account already exists.')
        if BookWork.objects.filter(title__startswith=FIXTURE_PREFIX).exists():
            raise CommandError('SALE delivery acceptance books already exist.')
        category = Category.objects.filter(name='Giáo trình', status='ACTIVE').first()
        if category is None:
            category = Category.objects.create(
                name='Giáo trình',
                slug='giao-trinh',
                description='Synthetic local category for acceptance fixture.',
                status='ACTIVE',
                created_at=timezone.now(),
                updated_at=timezone.now(),
            )

        now = timezone.now()
        with transaction.atomic():
            users = {
                key: User.objects.create(
                    email=email,
                    password_hash=make_password(FIXTURE_PASSWORD),
                    full_name=name,
                    role=role,
                    status='ACTIVE',
                    created_at=now,
                    updated_at=now,
                )
                for key, (email, name, role) in FIXTURE_USERS.items()
            }
            work = BookWork.objects.create(
                title=f'{FIXTURE_PREFIX}book',
                description='Synthetic local SALE delivery acceptance fixture.',
                author_name='Acceptance fixture',
                publisher_name='Acceptance fixture',
                category=category,
                created_by=users['seller'],
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
                owner=users['seller'],
                condition_label='like_new',
                status='AVAILABLE',
                created_at=now,
                updated_at=now,
            )
            listing = SaleListing.objects.create(
                book=book,
                seller=users['seller'],
                title=f'{FIXTURE_PREFIX}book',
                description='Synthetic local SALE delivery acceptance fixture.',
                price=Decimal('125000'),
                currency='VND',
                status='ACTIVE',
                published_at=now,
                created_at=now,
                updated_at=now,
            )
            cart = Cart.objects.create(
                user=users['customer'],
                status='ACTIVE',
                created_at=now,
                updated_at=now,
            )

        self.stdout.write(self.style.SUCCESS(
            'SALE delivery fixture ready: '
            f'customer={users["customer"].id}, seller={users["seller"].id}, '
            f'admin={users["admin"].id}, book={book.id}, listing={listing.id}, '
            f'cart={cart.id}. '
            f'Test password is {FIXTURE_PASSWORD}'
        ))

    def _cleanup(self):
        email_to_identity = {
            email: (name, role)
            for email, name, role in FIXTURE_USERS.values()
        }
        users = list(User.objects.filter(email__in=email_to_identity))
        for user in users:
            expected_name, expected_role = email_to_identity[user.email]
            if (user.full_name, user.role) != (expected_name, expected_role):
                raise CommandError(
                    f'Refusing to delete account with unexpected identity: {user.email}.',
                )
        user_ids = [user.id for user in users]
        carts = Cart.objects.filter(user_id__in=user_ids)
        cart_ids = list(carts.values_list('id', flat=True))
        checkout_groups = CheckoutGroup.objects.filter(cart__in=carts)
        checkout_group_ids = list(checkout_groups.values_list('id', flat=True))
        orders = Order.objects.filter(checkout_group__in=checkout_groups)
        order_ids = list(orders.values_list('id', flat=True))
        shipments = Shipment.objects.filter(order_id__in=order_ids)
        shipment_ids = list(shipments.values_list('id', flat=True))
        work_ids = list(
            BookWork.objects.filter(title__startswith=FIXTURE_PREFIX)
            .values_list('id', flat=True)
        )
        book_ids = list(
            Book.objects.filter(book_edition__book_work_id__in=work_ids)
            .values_list('id', flat=True)
        )
        listing_ids = list(
            SaleListing.objects.filter(
                title__startswith=FIXTURE_PREFIX,
                book_id__in=book_ids,
            ).values_list('id', flat=True)
        )

        with transaction.atomic():
            Notification.objects.filter(user_id__in=user_ids).delete()
            ShipmentTracking.objects.filter(shipment_id__in=shipment_ids).delete()
            Review.objects.filter(order_id__in=order_ids).delete()
            Refund.objects.filter(order_id__in=order_ids).delete()
            Return.objects.filter(order_id__in=order_ids).delete()
            SaleOrderItem.objects.filter(order_id__in=order_ids).delete()
            Payment.objects.filter(order_id__in=order_ids).delete()
            shipments.delete()
            orders.delete()
            checkout_groups.delete()
            CartItem.objects.filter(cart__in=carts).delete()
            carts.delete()
            SaleListing.objects.filter(id__in=listing_ids).delete()
            Book.objects.filter(id__in=book_ids).delete()
            BookEdition.objects.filter(book_work_id__in=work_ids).delete()
            BookWork.objects.filter(id__in=work_ids).delete()
            User.objects.filter(id__in=user_ids).delete()

        remaining = {
            'accounts': User.objects.filter(email__in=email_to_identity).count(),
            'carts': Cart.objects.filter(id__in=cart_ids).count(),
            'cart_items': CartItem.objects.filter(cart_id__in=cart_ids).count(),
            'checkout_groups': CheckoutGroup.objects.filter(id__in=checkout_group_ids).count(),
            'orders': Order.objects.filter(id__in=order_ids).count(),
            'sale_order_items': SaleOrderItem.objects.filter(order_id__in=order_ids).count(),
            'payments': Payment.objects.filter(order_id__in=order_ids).count(),
            'shipments': Shipment.objects.filter(id__in=shipment_ids).count(),
            'tracking': ShipmentTracking.objects.filter(shipment_id__in=shipment_ids).count(),
            'returns': Return.objects.filter(order_id__in=order_ids).count(),
            'refunds': Refund.objects.filter(order_id__in=order_ids).count(),
            'reviews': Review.objects.filter(order_id__in=order_ids).count(),
            'notifications': Notification.objects.filter(user_id__in=user_ids).count(),
            'books': Book.objects.filter(id__in=book_ids).count(),
            'listings': SaleListing.objects.filter(id__in=listing_ids).count(),
            'works': BookWork.objects.filter(title__startswith=FIXTURE_PREFIX).count(),
        }
        if any(remaining.values()):
            raise CommandError(f'Fixture cleanup incomplete: {remaining}')
        self.stdout.write(self.style.SUCCESS(f'SALE delivery fixtures cleaned: {remaining}'))
