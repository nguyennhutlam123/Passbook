import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, transaction
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from config.composite_admin import CompositeKeyAdmin
from books.models import (
    Book,
    BookReservation,
    Cart,
    CheckoutGroup,
    Order,
    Payment,
    SaleListing,
    SaleOrderItem,
)
from messaging.models import Conversation, ConversationMember
from notifications.models import Notification
from users.models import OtpVerification, University, User


FIXTURE_PREFIX = 'acceptance-fixture-'
FIXTURE_PASSWORD = 'AcceptanceOnly-Pass-42!'
LITE_TABLES = {
    model._meta.db_table
    for model in apps.get_models()
    if model._meta.app_label in {'users', 'books', 'messaging', 'notifications', 'reports'}
}


class Command(BaseCommand):
    help = 'Run database-backed acceptance checks against the confirmed local Lite test database.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-local-test-db', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm the local test target.')
        database = settings.DATABASES['default']
        expected_config = {
            'NAME': 'passbook_v12_lite_test',
            'HOST': '127.0.0.1',
            'PORT': '3308',
            'USER': 'root',
        }
        if any(str(database.get(key, '')) != value for key, value in expected_config.items()):
            raise CommandError('Refusing to run outside 127.0.0.1:3308/passbook_v12_lite_test.')
        if settings.PASSBOOK_ENVIRONMENT != 'test' or not settings.PASSBOOK_FAKE_PAYMENTS_ENABLED:
            raise CommandError('Use PASSBOOK_ENVIRONMENT=test and enable the local Fake Provider.')

        self.verify_live_schema_and_fixture()
        self.run_authentication_and_otp()
        self.run_api_workflows()
        self.run_concurrency_probes()
        self.run_admin_probes()
        self.run_performance_probes()
        self.stdout.write(self.style.SUCCESS('LOCAL LITE BACKEND ACCEPTANCE PROBES: PASS'))

    def verify_live_schema_and_fixture(self):
        ddl = (
            settings.BASE_DIR.parent.parent
            / 'docs/database/passbook_v1.2_lite.sql'
        ).read_text()
        table_definitions = re.findall(
            r'CREATE TABLE `([^`]+)` \(\n(.*?)\n\) ENGINE=',
            ddl,
            re.S,
        )
        expected_tables = {table for table, _body in table_definitions}
        if expected_tables != LITE_TABLES or len(expected_tables) != 41:
            raise CommandError('Django model/DDL mapping does not describe exactly 41 Lite tables.')

        expected_columns = {}
        expected_foreign_keys = set()
        expected_indexes = set()
        expected_checks = set(re.findall(
            r'CONSTRAINT `([^`]+)` CHECK \(',
            ddl,
        ))
        for table, body in table_definitions:
            expected_columns[table] = {
                match.group(1)
                for match in re.finditer(r'^  `([^`]+)` ', body, re.M)
            }
            for name, local, parent, remote in re.findall(
                r'CONSTRAINT `([^`]+)` FOREIGN KEY \(([^)]+)\) '
                r'REFERENCES `([^`]+)` \(([^)]+)\)',
                body,
            ):
                expected_foreign_keys.add((
                    table,
                    name,
                    tuple(re.findall(r'`([^`]+)`', local)),
                    parent,
                    tuple(re.findall(r'`([^`]+)`', remote)),
                ))
            indexes = [
                ('PRIMARY', match.group(1))
                for match in re.finditer(r'^  PRIMARY KEY \(([^)]+)\)', body, re.M)
            ]
            indexes.extend(
                (name, columns)
                for name, columns in re.findall(
                    r'^  (?:UNIQUE KEY|KEY) `([^`]+)` \(([^)]+)\)',
                    body,
                    re.M,
                )
            )
            indexes.extend(
                (name, columns)
                for name, columns in re.findall(
                    r'CONSTRAINT `([^`]+)` UNIQUE \(([^)]+)\)',
                    body,
                )
            )
            expected_indexes.update(
                (
                    table,
                    name,
                    tuple(re.findall(r'`([^`]+)`', columns)),
                )
                for name, columns in indexes
            )

        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), VERSION()')
            database_name, version = cursor.fetchone()
            live_tables = set(connection.introspection.table_names(cursor))
            missing_tables = expected_tables - live_tables
            if database_name != 'passbook_v12_lite_test' or missing_tables:
                raise CommandError(
                    f'Unexpected live DB {database_name}; missing Lite tables: {sorted(missing_tables)}',
                )
            cursor.execute(
                '''
                SELECT TABLE_NAME, COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE()
                ''',
            )
            actual_columns = {}
            for table, column in cursor.fetchall():
                if table in expected_tables:
                    actual_columns.setdefault(table, set()).add(column)
            column_differences = {
                table: (
                    sorted(expected_columns[table] - actual_columns.get(table, set())),
                    sorted(actual_columns.get(table, set()) - expected_columns[table]),
                )
                for table in expected_tables
                if expected_columns[table] != actual_columns.get(table, set())
            }
            if column_differences:
                raise CommandError(f'Live Lite columns differ from DDL: {column_differences}')
            cursor.execute(
                '''
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
                ''',
            )
            foreign_key_rows = cursor.fetchall()
            cursor.execute(
                '''
                SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
                       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
                ''',
            )
            actual_fk_groups = {}
            for table, name, column, parent, parent_column, ordinal in cursor.fetchall():
                if table in expected_tables:
                    group = actual_fk_groups.setdefault(
                        (table, name, parent),
                        ([], []),
                    )
                    group[0].append(column)
                    group[1].append(parent_column)
            actual_foreign_keys = {
                (table, name, tuple(columns), parent, tuple(parent_columns))
                for (table, name, parent), (columns, parent_columns)
                in actual_fk_groups.items()
            }
            if actual_foreign_keys != expected_foreign_keys:
                raise CommandError(
                    'Live Lite foreign keys differ from DDL: '
                    f'missing={sorted(expected_foreign_keys - actual_foreign_keys)}, '
                    f'extra={sorted(actual_foreign_keys - expected_foreign_keys)}',
                )
            cursor.execute(
                '''
                SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA=DATABASE()
                ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
                ''',
            )
            actual_index_groups = {}
            for table, name, column, ordinal in cursor.fetchall():
                if table in expected_tables:
                    actual_index_groups.setdefault((table, name), []).append(column)
            actual_indexes = {
                (table, name, tuple(columns))
                for (table, name), columns in actual_index_groups.items()
            }
            implicit_fk_indexes = {
                (table, name, local_columns)
                for table, name, local_columns, _parent, _remote in expected_foreign_keys
                if (table, name, local_columns) in actual_indexes
                and not any(
                    index_table == table
                    and index_columns[:len(local_columns)] == local_columns
                    for index_table, _index_name, index_columns in expected_indexes
                )
            }
            comparable_indexes = actual_indexes - implicit_fk_indexes
            if comparable_indexes != expected_indexes:
                raise CommandError(
                    'Live Lite indexes differ from DDL: '
                    f'missing={sorted(expected_indexes - comparable_indexes)}, '
                    f'extra={sorted(comparable_indexes - expected_indexes)}',
                )
            cursor.execute(
                '''
                SELECT TABLE_NAME, CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA=DATABASE() AND CONSTRAINT_TYPE='CHECK'
                ''',
            )
            actual_checks = {
                name for table, name in cursor.fetchall()
                if table in expected_tables
            }
            if not expected_checks.issubset(actual_checks):
                raise CommandError(
                    'Live Lite CHECK constraints differ from DDL: '
                    f'missing={sorted(expected_checks - actual_checks)}',
                )
            cursor.execute(
                '''
                SELECT CHECK_CLAUSE
                FROM information_schema.CHECK_CONSTRAINTS
                WHERE CONSTRAINT_SCHEMA=DATABASE()
                  AND CONSTRAINT_NAME='ck_sale_listings_3'
                ''',
            )
            sale_status_check = cursor.fetchone()
            if (
                sale_status_check is None
                or 'PENDING' not in sale_status_check[0]
                or 'REJECTED' not in sale_status_check[0]
            ):
                raise CommandError('Live sale listing status constraint lacks moderation states.')

        orphans = []
        with connection.cursor() as cursor:
            for table, column, parent, parent_column in foreign_key_rows:
                if table not in expected_tables:
                    continue
                cursor.execute(
                    f'SELECT COUNT(*) FROM `{table}` child '
                    f'LEFT JOIN `{parent}` parent '
                    f'ON child.`{column}`=parent.`{parent_column}` '
                    f'WHERE child.`{column}` IS NOT NULL '
                    f'AND parent.`{parent_column}` IS NULL',
                )
                count = cursor.fetchone()[0]
                if count:
                    orphans.append((table, column, parent, count))
        if orphans:
            raise CommandError(f'Live database contains orphan foreign keys: {orphans}')

        counts = {
            'books': SaleListing.objects.filter(
                title__startswith=FIXTURE_PREFIX,
            ).count(),
            'users': User.objects.filter(email__startswith=FIXTURE_PREFIX).count(),
        }
        if counts['books'] < 100 or counts['users'] < 10:
            raise CommandError(f'Acceptance dataset is too small: {counts}')
        self.stdout.write(
            f'LIVE DB PASS: {database_name} MariaDB {version}; '
            f'{len(expected_tables)}/41 Lite tables; exact columns, '
            f'{len(expected_foreign_keys)} FKs, {len(expected_indexes)} declared indexes, '
            f'{len(expected_checks)} declared checks '
            f'(+{len(implicit_fk_indexes)} engine FK index); zero orphans; '
            f'{counts["books"]} seeded books; {counts["users"]} seeded users.',
        )

    def run_authentication_and_otp(self):
        with transaction.atomic():
            try:
                with self._local_email_settings():
                    client = APIClient()
                    email = f'{FIXTURE_PREFIX}buyer_1@example.invalid'
                    invalid = client.post(
                        '/api/auth/login/',
                        {'email': email, 'password': 'invalid-password'},
                        format='json',
                    )
                    self.assert_status(invalid, 401, 'invalid password')

                    login = client.post(
                        '/api/auth/login/',
                        {'email': email, 'password': FIXTURE_PASSWORD},
                        format='json',
                    )
                    self.assert_status(login, 200, 'login')
                    refresh = client.post(
                        '/api/auth/token/refresh/',
                        {'refresh': login.data['refresh']},
                        format='json',
                    )
                    self.assert_status(refresh, 200, 'refresh')
                    authenticated = APIClient()
                    authenticated.credentials(
                        HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}',
                    )
                    self.assert_status(authenticated.get('/api/auth/profile/'), 200, 'profile')
                    logout = authenticated.post(
                        '/api/auth/logout/',
                        {'refresh': login.data['refresh']},
                        format='json',
                    )
                    self.assert_status(logout, 204, 'logout')
                    self.assert_status(
                        authenticated.get('/api/auth/profile/'),
                        401,
                        'revoked access token',
                    )
                    self.assert_status(
                        client.post(
                            '/api/auth/token/refresh/',
                            {'refresh': login.data['refresh']},
                            format='json',
                        ),
                        401,
                        'revoked refresh token',
                    )

                    expired_access = self.expired_access_token(
                        User.objects.get(email=email),
                    )
                    expired_client = APIClient()
                    expired_client.credentials(
                        HTTP_AUTHORIZATION=f'Bearer {expired_access}',
                    )
                    self.assert_status(
                        expired_client.get('/api/auth/profile/'),
                        401,
                        'expired access token',
                    )

                    user = User.objects.get(email=email)
                    user.status = 'BLOCKED'
                    user.save(update_fields=['status'])
                    blocked_login = client.post(
                        '/api/auth/login/',
                        {'email': email, 'password': FIXTURE_PASSWORD},
                        format='json',
                    )
                    self.assert_status(blocked_login, 403, 'blocked account login')
                    user.status = 'ACTIVE'
                    user.save(update_fields=['status'])

                    register_email = f'{FIXTURE_PREFIX}integration@example.invalid'
                    register = client.post('/api/auth/register/', {
                        'name': 'Acceptance Integration User',
                        'email': register_email,
                        'password': 'Acceptance-Integration-43!',
                        'university_id': University.objects.first().id,
                    }, format='json')
                    self.assert_status(register, 202, 'register')
                    register_code = self.otp_from_latest_email()
                    verify = client.post('/api/auth/verify-otp/', {
                        'target': register_email,
                        'purpose': 'REGISTER',
                        'otp': register_code,
                    }, format='json')
                    self.assert_status(verify, 200, 'register OTP')
                    if User.objects.get(email=register_email).status != 'ACTIVE':
                        raise CommandError('REGISTER OTP did not activate the account.')

                    otp_target = email
                    self.assert_status(client.post('/api/auth/resend-otp/', {
                        'target': otp_target,
                        'purpose': 'LOGIN',
                    }, format='json'), 202, 'OTP request')
                    invalid_code = '000000'
                    issued_code = self.otp_from_latest_email()
                    if invalid_code == issued_code:
                        invalid_code = '000001'
                    for _ in range(2):
                        invalid_otp = client.post('/api/auth/verify-otp/', {
                            'target': otp_target,
                            'purpose': 'LOGIN',
                            'otp': invalid_code,
                        }, format='json')
                        self.assert_status(invalid_otp, 400, 'invalid OTP')
                    blocked_otp = OtpVerification.objects.filter(
                        target=otp_target,
                        purpose='LOGIN',
                    ).latest('id')
                    if blocked_otp.status != 'BLOCKED':
                        raise CommandError('OTP attempt limit did not block the challenge.')

                    self.assert_status(client.post('/api/auth/resend-otp/', {
                        'target': otp_target,
                        'purpose': 'LOGIN',
                    }, format='json'), 202, 'OTP resend')
                    self.assert_status(client.post('/api/auth/resend-otp/', {
                        'target': otp_target,
                        'purpose': 'LOGIN',
                    }, format='json'), 429, 'OTP resend limit')
                    valid_login_code = self.otp_from_latest_email()
                    verified_login = client.post('/api/auth/verify-otp/', {
                        'target': otp_target,
                        'purpose': 'LOGIN',
                        'otp': valid_login_code,
                    }, format='json')
                    self.assert_status(verified_login, 200, 'valid login OTP')

                    expired = OtpVerification.objects.create(
                        user=None,
                        channel='EMAIL',
                        purpose='LOGIN',
                        target=f'{FIXTURE_PREFIX}expired@example.invalid',
                        otp_hash=make_password('123456'),
                        expires_at=timezone.now() - timedelta(seconds=1),
                        attempt_count=0,
                        resend_count=0,
                        status='PENDING',
                        created_at=timezone.now() - timedelta(minutes=10),
                        updated_at=timezone.now() - timedelta(minutes=10),
                    )
                    self.assert_status(client.post('/api/auth/verify-otp/', {
                        'target': expired.target,
                        'purpose': 'LOGIN',
                        'otp': '123456',
                    }, format='json'), 400, 'expired OTP')
                    expired.refresh_from_db()
                    if expired.status != 'EXPIRED':
                        raise CommandError('Expired OTP was not marked EXPIRED.')

                    self.assert_status(client.post('/api/auth/forgot-password/', {
                        'target': email,
                    }, format='json'), 202, 'forgot password')
                    reset_code = self.otp_from_latest_email()
                    verified_reset = client.post('/api/auth/verify-otp/', {
                        'target': email,
                        'purpose': 'FORGOT_PASSWORD',
                        'otp': reset_code,
                    }, format='json')
                    self.assert_status(verified_reset, 200, 'reset OTP')
                    reset = client.post('/api/auth/reset-password/', {
                        'reset_token': verified_reset.data['reset_token'],
                        'new_password': 'Acceptance-Reset-44!',
                    }, format='json')
                    self.assert_status(reset, 200, 'reset password')
                    self.assert_status(client.post('/api/auth/login/', {
                        'email': email,
                        'password': 'Acceptance-Reset-44!',
                    }, format='json'), 200, 'login after reset')
            finally:
                transaction.set_rollback(True)
        self.stdout.write('AUTH/OTP PASS: login, invalid password, token expiry/refresh/logout, status lock, registration, OTP expiry/attempt/resend limits, password reset.')

    def run_api_workflows(self):
        buyer = User.objects.get(email=f'{FIXTURE_PREFIX}buyer_1@example.invalid')
        other_buyer = User.objects.get(email=f'{FIXTURE_PREFIX}buyer_2@example.invalid')
        seller = User.objects.get(email=f'{FIXTURE_PREFIX}seller_1@example.invalid')
        lender = User.objects.get(email=f'{FIXTURE_PREFIX}seller_2@example.invalid')
        admin_user = User.objects.get(email=f'{FIXTURE_PREFIX}admin@example.invalid')
        buyer_client = self.api_client(buyer)
        other_client = self.api_client(other_buyer)
        seller_client = self.api_client(seller)
        lender_client = self.api_client(lender)
        admin_client = self.api_client(admin_user)

        with transaction.atomic():
            try:
                listing_book = Book.objects.filter(
                    status='AVAILABLE',
                    sale_listings__status='ACTIVE',
                ).exclude(
                    reservations__status__in=('PENDING', 'CONFIRMED'),
                ).first()
                if listing_book is None:
                    raise CommandError('No available listing for API state tests.')
                self.assert_status(
                    buyer_client.patch(
                        '/api/auth/profile/',
                        {'name': 'Acceptance Profile Updated'},
                        format='json',
                    ),
                    200,
                    'profile update',
                )
                address = buyer.addresses.first()
                self.assert_status(
                    buyer_client.patch(
                        f'/api/users/addresses/{address.id}/',
                        {'address_line': 'Acceptance address updated'},
                        format='json',
                    ),
                    200,
                    'address update',
                )
                self.assert_status(
                    other_client.patch(
                        f'/api/users/addresses/{address.id}/',
                        {'address_line': 'Forbidden'},
                        format='json',
                    ),
                    404,
                    'address ownership',
                )
                self.assert_status(
                    buyer_client.get(f'/api/users/{seller.id}/profile/'),
                    200,
                    'seller profile',
                )
                self.assert_status(
                    buyer_client.get('/api/books/?page=1&page_size=20'),
                    200,
                    'books page',
                )
                self.assert_status(
                    buyer_client.get(
                        '/api/books/?search=acceptance-fixture-book&sort=price_asc&page_size=20',
                    ),
                    200,
                    'book search/sort',
                )
                self.assert_status(
                    buyer_client.get(f'/api/books/{listing_book.id}/'),
                    200,
                    'book detail',
                )
                created_book = seller_client.post(
                    '/api/books/',
                    {
                        'title': f'{FIXTURE_PREFIX}moderation-{uuid4().hex}',
                        'description': 'Synthetic listing moderation test',
                        'price': '90000.0000',
                        'condition_status': 'good',
                    },
                    format='json',
                )
                self.assert_status(created_book, 201, 'book submission for moderation')
                if created_book.data['price'] != '90000.0000':
                    raise CommandError('Book submission response omitted its pending listing price.')
                pending_listing = SaleListing.objects.get(
                    book_id=created_book.data['id'],
                )
                if pending_listing.status != 'PENDING' or pending_listing.published_at:
                    raise CommandError('New seller listing was not held for moderation.')
                self.assert_status(
                    seller_client.patch(
                        f'/api/sale-listings/{pending_listing.id}/',
                        {'status': 'ACTIVE'},
                        format='json',
                    ),
                    400,
                    'seller cannot bypass listing moderation',
                )
                public_listings = buyer_client.get(
                    f'/api/sale-listings/?search={pending_listing.title}',
                )
                self.assert_status(public_listings, 200, 'public listing moderation visibility')
                if any(
                    item['id'] == pending_listing.id
                    for item in public_listings.data['results']
                ):
                    raise CommandError('Pending listing leaked into public marketplace results.')
                rejected_listing = SaleListing.objects.filter(
                    title__startswith=FIXTURE_PREFIX,
                    status='REJECTED',
                ).first()
                if rejected_listing is None:
                    raise CommandError('Rejected listing fixture is required.')
                rejected_owner_client = self.api_client(rejected_listing.seller)
                resubmitted = rejected_owner_client.patch(
                    f'/api/sale-listings/{rejected_listing.id}/',
                    {'title': f'{rejected_listing.title} revised'},
                    format='json',
                )
                self.assert_status(resubmitted, 200, 'rejected listing resubmission')
                rejected_listing.refresh_from_db()
                if rejected_listing.status != 'PENDING':
                    raise CommandError('Editing a rejected listing did not resubmit it.')
                rejected_listing.status = 'REJECTED'
                rejected_listing.save(update_fields=['status'])
                owned_listing = SaleListing.objects.filter(
                    seller=seller,
                    status='ACTIVE',
                    book__status='AVAILABLE',
                ).first()
                if owned_listing is None:
                    raise CommandError('No active seller-owned listing for CRUD checks.')
                self.assert_status(
                    seller_client.patch(
                        f'/api/sale-listings/{owned_listing.id}/',
                        {'title': 'Acceptance listing edit', 'price': '123456.0000'},
                        format='json',
                    ),
                    200,
                    'listing update',
                )
                self.assert_status(
                    other_client.patch(
                        f'/api/sale-listings/{owned_listing.id}/',
                        {'title': 'Unauthorized update'},
                        format='json',
                    ),
                    403,
                    'listing ownership',
                )
                image = seller_client.post(
                    f'/api/books/{owned_listing.book_id}/images/',
                    {
                        'image_url': (
                            'https://res.cloudinary.com/demo/image/upload/'
                            f'{uuid4().hex}.jpg'
                        ),
                        'is_primary': True,
                        'sort_order': 1,
                    },
                    format='json',
                )
                self.assert_status(image, 201, 'HTTPS image record')
                self.assert_status(
                    seller_client.patch(
                        f'/api/books/{owned_listing.book_id}/images/{image.data["id"]}/',
                        {'sort_order': 2},
                        format='json',
                    ),
                    200,
                    'image update',
                )
                self.assert_status(
                    seller_client.delete(
                        f'/api/books/{owned_listing.book_id}/images/{image.data["id"]}/',
                    ),
                    204,
                    'image delete',
                )
                self.assert_status(
                    buyer_client.get('/api/favorites/?page_size=20'),
                    200,
                    'favorites',
                )
                self.assert_status(
                    buyer_client.get('/api/orders/?page_size=20'),
                    200,
                    'orders',
                )
                conversation_id = ConversationMember.objects.filter(
                    user=buyer,
                ).values_list('conversation_id', flat=True).first()
                if conversation_id is None:
                    raise CommandError('No seeded conversation is available.')
                self.assert_status(
                    buyer_client.post(
                        f'/api/conversations/{conversation_id}/messages/',
                        {'content': 'Acceptance integration message'},
                        format='json',
                    ),
                    201,
                    'message create',
                )
                self.assert_status(
                    buyer_client.get(
                        f'/api/conversations/{conversation_id}/messages/?page_size=50',
                    ),
                    200,
                    'message list',
                )
                self.assert_status(
                    buyer_client.get('/api/notifications/?page_size=20'),
                    200,
                    'notifications',
                )
                unread_notification = Notification.objects.filter(
                    user=buyer,
                    is_read=False,
                ).first()
                if unread_notification is not None:
                    self.assert_status(
                        buyer_client.patch(
                            f'/api/notifications/{unread_notification.id}/read/',
                            {},
                            format='json',
                        ),
                        200,
                        'notification read',
                    )

                favorite = buyer_client.post(
                    f'/api/books/{listing_book.id}/favorite/',
                    {},
                    format='json',
                )
                self.assert_status(favorite, (200, 201), 'favorite create/retry')
                self.assert_status(
                    buyer_client.post(
                        f'/api/books/{listing_book.id}/favorite/',
                        {},
                        format='json',
                    ),
                    200,
                    'favorite idempotent retry',
                )
                self.assert_status(
                    buyer_client.delete(f'/api/books/{listing_book.id}/favorite/'),
                    204,
                    'favorite delete',
                )

                reservation = buyer_client.post(
                    f'/api/books/{listing_book.id}/reservations/',
                    {'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()},
                    format='json',
                )
                self.assert_status(reservation, 201, 'reservation create')
                reservation_id = reservation.data['id']
                self.assert_status(
                    seller_client.post(
                        f'/api/book-reservations/{reservation_id}/confirm/',
                        {},
                        format='json',
                    ),
                    200,
                    'reservation confirm',
                )
                cancelled = buyer_client.post(
                    f'/api/book-reservations/{reservation_id}/cancel/',
                    {},
                    format='json',
                )
                self.assert_status(cancelled, 200, 'reservation cancel')
                self.assert_status(
                    buyer_client.post(
                        f'/api/book-reservations/{reservation_id}/cancel/',
                        {},
                        format='json',
                    ),
                    400,
                    'invalid reservation transition',
                )
                expired_reservation = buyer_client.post(
                    f'/api/books/{listing_book.id}/reservations/',
                    {'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()},
                    format='json',
                )
                self.assert_status(expired_reservation, 201, 'reservation expiry fixture')
                expired_id = expired_reservation.data['id']
                expired_at = timezone.now() - timedelta(hours=1)
                BookReservation.objects.filter(pk=expired_id).update(
                    created_at=expired_at - timedelta(hours=1),
                    expires_at=expired_at,
                )
                self.assert_status(
                    buyer_client.get('/api/book-reservations/'),
                    200,
                    'reservation expiry sweep',
                )
                if BookReservation.objects.get(pk=expired_id).status != 'EXPIRED':
                    raise CommandError('Expired reservation did not persist EXPIRED.')
                self.assert_status(
                    buyer_client.post(
                        f'/api/book-reservations/{expired_id}/cancel/',
                        {},
                        format='json',
                    ),
                    400,
                    'invalid expired reservation transition',
                )

                checkout_data = {
                    'idempotency_key': f'{FIXTURE_PREFIX}acceptance-checkout-{uuid4().hex}',
                    'shipping_address_snapshot': {
                        'recipient_name': buyer.full_name,
                        'phone': buyer.phone,
                        'address_line': 'Synthetic local acceptance address',
                    },
                }
                checkout = buyer_client.post(
                    '/api/checkout/',
                    checkout_data,
                    format='json',
                )
                self.assert_status(checkout, 201, 'checkout')
                checkout_retry = buyer_client.post(
                    '/api/checkout/',
                    checkout_data,
                    format='json',
                )
                self.assert_status(checkout_retry, 200, 'checkout retry')
                if checkout.data['id'] != checkout_retry.data['id']:
                    raise CommandError('Checkout retry created a duplicate checkout group.')
                first_cancelled_order = None
                for order_payload in checkout.data['orders']:
                    self.assert_status(
                        buyer_client.post(
                            f'/api/orders/{order_payload["id"]}/cancel/',
                            {},
                            format='json',
                        ),
                        200,
                        'order cancellation',
                    )
                    first_cancelled_order = (
                        first_cancelled_order or order_payload['id']
                    )
                if first_cancelled_order is not None:
                    self.assert_status(
                        buyer_client.post(
                            f'/api/orders/{first_cancelled_order}/cancel/',
                            {},
                            format='json',
                        ),
                        400,
                        'invalid order cancellation',
                    )

                sale_order = Order.objects.get(order_code='ORD-acceptance-fixture-1')
                self.exercise_sale_payment_fulfillment(
                    buyer_client,
                    seller_client,
                    admin_client,
                    sale_order,
                )
                self.exercise_fake_payment_failure_and_cancel(
                    buyer_client,
                    admin_client,
                    Order.objects.get(order_code='ORD-acceptance-fixture-2'),
                )
                borrow = apps.get_model('books', 'BorrowOrder').objects.get(
                    order__order_code='BOR-acceptance-fixture-borrow-1',
                )
                self.exercise_borrow_lifecycle(
                    buyer_client,
                    other_client,
                    lender_client,
                    admin_client,
                    borrow,
                )

                request = buyer_client.post('/api/book-requests/', {
                    'request_type': 'BUY',
                    'title_keyword': 'acceptance-fixture-book',
                    'budget_max': '500000',
                    'condition_preference': 'good',
                }, format='json')
                self.assert_status(request, 201, 'book request')
                matches = buyer_client.get(
                    f'/api/book-requests/{request.data["id"]}/matches/',
                )
                self.assert_status(matches, 200, 'request matches')
                if not matches.data:
                    raise CommandError('Seeded listings did not produce a request match.')
                interest = other_client.post(
                    f'/api/book-requests/{request.data["id"]}/interests/',
                    {'note': 'Acceptance interest'},
                    format='json',
                )
                self.assert_status(interest, 201, 'request interest')
                interest_retry = other_client.post(
                    f'/api/book-requests/{request.data["id"]}/interests/',
                    {'note': 'Acceptance interest retry'},
                    format='json',
                )
                self.assert_status(interest_retry, 200, 'request interest retry')
                borrow_request = buyer_client.post('/api/book-requests/', {
                    'request_type': 'BORROW',
                    'title_keyword': f'{FIXTURE_PREFIX}lend-1',
                    'budget_max': '100000',
                }, format='json')
                self.assert_status(borrow_request, 201, 'borrow request')
                borrow_matches = buyer_client.get(
                    f'/api/book-requests/{borrow_request.data["id"]}/matches/',
                )
                self.assert_status(borrow_matches, 200, 'borrow request matches')
                if not borrow_matches.data or borrow_matches.data[0]['match_type'] != 'BORROW':
                    raise CommandError('Active lend listing did not match a borrow request.')
                sell_request = seller_client.post('/api/book-requests/', {
                    'request_type': 'SELL_INTENT',
                    'title_keyword': 'acceptance-fixture-book',
                    'asking_price': '100000',
                    'currency': 'VND',
                }, format='json')
                self.assert_status(sell_request, 201, 'sell intent request')
                sell_matches = seller_client.get(
                    f'/api/book-requests/{sell_request.data["id"]}/matches/',
                )
                self.assert_status(sell_matches, 200, 'sell intent matches')
                matching_buy = next(
                    (
                        item for item in sell_matches.data
                        if item.get('matched_request_id') == request.data['id']
                    ),
                    None,
                )
                if matching_buy is None or matching_buy['match_type'] != 'BUY_SELL':
                    raise CommandError('SELL_INTENT did not match the compatible BUY request.')
                sell_retry = seller_client.get(
                    f'/api/book-requests/{sell_request.data["id"]}/matches/',
                )
                self.assert_status(sell_retry, 200, 'sell intent match retry')
                retry_match = next(
                    (
                        item for item in sell_retry.data
                        if item.get('matched_request_id') == request.data['id']
                    ),
                    None,
                )
                if retry_match is None or retry_match['id'] != matching_buy['id']:
                    raise CommandError('Request match retry created duplicate matches.')
                buy_matches = buyer_client.get(
                    f'/api/book-requests/{request.data["id"]}/matches/',
                )
                self.assert_status(buy_matches, 200, 'buy request sell-intent matches')
                if not any(
                    item.get('matched_request_id') == sell_request.data['id']
                    for item in buy_matches.data
                ):
                    raise CommandError('BUY request did not discover the matching SELL_INTENT.')

                completed_order = Order.objects.get(
                    order_code='ORD-acceptance-fixture-3',
                )
                self.assert_status(
                    other_client.post(
                        f'/api/orders/{completed_order.id}/reviews/',
                        {'rating': 5, 'comment': 'Acceptance review'},
                        format='json',
                    ),
                    200,
                    'review upsert',
                )
                report_data = {
                    'sale_listing_id': listing_book.sale_listings.filter(
                        status='ACTIVE',
                    ).first().id,
                    'reason': f'ACCEPTANCE-{uuid4().hex}',
                    'description': 'Synthetic acceptance report',
                }
                report = buyer_client.post(
                    '/api/reports/',
                    report_data,
                    format='json',
                )
                self.assert_status(
                    report,
                    201,
                    'report create',
                )
                report_retry = buyer_client.post(
                    '/api/reports/',
                    report_data,
                    format='json',
                )
                self.assert_status(report_retry, 200, 'report idempotent retry')
                self.assert_status(admin_client.get('/api/admin/reports/'), 200, 'admin reports')
                dashboard = admin_client.get('/api/admin/dashboard/')
                self.assert_status(dashboard, 200, 'admin dashboard')
                if 'shipments' not in dashboard.data:
                    raise CommandError('Dashboard response omitted shipment metrics.')
                listing_metrics = dashboard.data['listings']
                if (
                    not listing_metrics['pending_status_supported']
                    or not listing_metrics['rejected_status_supported']
                    or listing_metrics['pending'] < 1
                    or listing_metrics['rejected'] < 1
                ):
                    raise CommandError(
                        'Dashboard does not report live pending/rejected listing counts.',
                    )
            finally:
                transaction.set_rollback(True)
        self.stdout.write('API WORKFLOWS PASS: marketplace, reservation, cart/checkout retry/cancel, sale payment/shipping/return/refund, borrow, favorites, messaging, notifications, requests/matching/interests, reviews/reports, dashboard.')

    def exercise_sale_payment_fulfillment(
        self,
        buyer_client,
        seller_client,
        admin_client,
        order,
    ):
        key = f'{FIXTURE_PREFIX}acceptance-payment-{uuid4().hex}'
        payment = buyer_client.post(
            f'/api/orders/{order.id}/payments/',
            {'provider': 'fake', 'payment_method': 'TEST', 'idempotency_key': key},
            format='json',
        )
        self.assert_status(payment, 201, 'fake payment intent')
        payment_id = payment.data['id']
        retry = buyer_client.post(
            f'/api/orders/{order.id}/payments/',
            {'provider': 'fake', 'payment_method': 'TEST', 'idempotency_key': key},
            format='json',
        )
        self.assert_status(retry, 200, 'fake payment retry')
        if retry.data['id'] != payment_id:
            raise CommandError('Payment retry created a duplicate intent.')
        paid = admin_client.post(
            f'/api/admin/fake-payments/{payment_id}/transition/',
            {'status': 'PAID'},
            format='json',
        )
        self.assert_status(paid, 200, 'fake payment success')
        if paid.data['status'] != 'PAID':
            raise CommandError('Fake payment success did not persist PAID.')
        shipment = seller_client.post(
            f'/api/orders/{order.id}/shipments/',
            {
                'carrier': 'FAKE',
                'tracking_code': f'ACCEPTANCE-{uuid4().hex}',
            },
            format='json',
        )
        self.assert_status(shipment, 201, 'shipment create')
        shipment_id = shipment.data['id']
        for tracking_status in ('SHIPPED', 'IN_TRANSIT', 'DELIVERED'):
            event = seller_client.post(
                f'/api/shipments/{shipment_id}/tracking/',
                {'status': tracking_status, 'location': 'Local test'},
                format='json',
            )
            self.assert_status(event, 201, f'shipment {tracking_status}')
        item_id = order.sale_items.first().id
        return_response = buyer_client.post(
            f'/api/orders/{order.id}/returns/',
            {'sale_order_item_id': item_id, 'reason': 'ACCEPTANCE_TEST'},
            format='json',
        )
        self.assert_status(return_response, 201, 'return request')
        return_id = return_response.data['id']
        for action in ('approve', 'complete'):
            self.assert_status(
                seller_client.post(
                    f'/api/returns/{return_id}/{action}/',
                    {},
                    format='json',
                ),
                200,
                f'return {action}',
            )
        refund_data = {
            'payment_id': payment_id,
            'return_id': return_id,
            'idempotency_key': f'{FIXTURE_PREFIX}acceptance-refund-{uuid4().hex}',
            'reason': 'ACCEPTANCE_TEST',
            'amount': str(order.total_amount),
        }
        refund = buyer_client.post(
            f'/api/orders/{order.id}/refunds/',
            refund_data,
            format='json',
        )
        self.assert_status(refund, 201, 'refund request')
        refund_retry = buyer_client.post(
            f'/api/orders/{order.id}/refunds/',
            refund_data,
            format='json',
        )
        self.assert_status(refund_retry, 200, 'refund idempotent retry')
        if refund_retry.data['id'] != refund.data['id']:
            raise CommandError('Refund retry created a duplicate row.')
        failed = admin_client.post(
            f'/api/admin/fake-refunds/{refund.data["id"]}/transition/',
            {'status': 'FAILED'},
            format='json',
        )
        self.assert_status(failed, 200, 'fake refund failure')
        completed = admin_client.post(
            f'/api/admin/fake-refunds/{refund.data["id"]}/transition/',
            {'status': 'COMPLETED'},
            format='json',
        )
        self.assert_status(completed, 200, 'fake refund completion')
        if completed.data['status'] != 'COMPLETED':
            raise CommandError('Fake refund did not complete.')
        self.assert_status(
            admin_client.post(
                f'/api/admin/fake-refunds/{refund.data["id"]}/transition/',
                {'status': 'COMPLETED'},
                format='json',
            ),
            200,
            'fake refund completion retry',
        )

    def exercise_fake_payment_failure_and_cancel(
        self,
        buyer_client,
        admin_client,
        order,
    ):
        key = f'{FIXTURE_PREFIX}acceptance-payment-failure-{uuid4().hex}'
        payment = buyer_client.post(
            f'/api/orders/{order.id}/payments/',
            {'provider': 'fake', 'payment_method': 'TEST', 'idempotency_key': key},
            format='json',
        )
        self.assert_status(payment, 201, 'fake failed payment intent')
        payment_id = payment.data['id']
        for target_status in ('FAILED', 'PENDING', 'CANCELLED'):
            transitioned = admin_client.post(
                f'/api/admin/fake-payments/{payment_id}/transition/',
                {'status': target_status},
                format='json',
            )
            self.assert_status(
                transitioned,
                200,
                f'fake payment {target_status}',
            )
            if transitioned.data['status'] != target_status:
                raise CommandError(f'Payment transition failed to reach {target_status}.')
        self.assert_status(
            admin_client.post(
                f'/api/admin/fake-payments/{payment_id}/transition/',
                {'status': 'PAID'},
                format='json',
            ),
            400,
            'invalid cancelled payment transition',
        )

    def exercise_borrow_lifecycle(
        self,
        buyer_client,
        other_client,
        lender_client,
        admin_client,
        borrow,
    ):
        payment = other_client.post(
            f'/api/orders/{borrow.order_id}/payments/',
            {
                'provider': 'fake',
                'payment_method': 'TEST',
                'idempotency_key': f'{FIXTURE_PREFIX}acceptance-borrow-{uuid4().hex}',
            },
            format='json',
        )
        self.assert_status(payment, 201, 'borrow payment intent')
        self.assert_status(
            admin_client.post(
                f'/api/admin/fake-payments/{payment.data["id"]}/transition/',
                {'status': 'PAID'},
                format='json',
            ),
            200,
            'borrow payment success',
        )
        for client, action, expected in (
            (lender_client, 'confirm', 'CONFIRMED'),
            (lender_client, 'ready', 'READY_FOR_PICKUP'),
            (other_client, 'start', 'ACTIVE'),
            (other_client, 'request-return', 'RETURN_REQUESTED'),
            (lender_client, 'return', 'RETURNED'),
            (other_client, 'complete', 'COMPLETED'),
        ):
            response = client.post(
                f'/api/borrow-orders/{borrow.id}/{action}/',
                {},
                format='json',
            )
            self.assert_status(response, 200, f'borrow {action}')
            if response.data['status'] != expected:
                raise CommandError(f'Borrow {action} resulted in {response.data["status"]}.')
        invalid = other_client.post(
            f'/api/borrow-orders/{borrow.id}/complete/',
            {},
            format='json',
        )
        self.assert_status(invalid, 400, 'invalid borrow transition')

    def run_concurrency_probes(self):
        buyer_one = User.objects.get(email=f'{FIXTURE_PREFIX}buyer_1@example.invalid')
        buyer_two = User.objects.get(email=f'{FIXTURE_PREFIX}buyer_2@example.invalid')
        barrier = threading.Barrier(2)
        book = Book.objects.filter(
            status='AVAILABLE',
            sale_listings__status='ACTIVE',
        ).exclude(
            owner_id__in=(buyer_one.id, buyer_two.id),
        ).exclude(
            reservations__status__in=('PENDING', 'CONFIRMED'),
        ).first()
        if book is None:
            raise CommandError('No listing is available for concurrency probes.')

        def reserve(user_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                client = self.api_client(user)
                barrier.wait(timeout=20)
                response = client.post(
                    f'/api/books/{book.id}/reservations/',
                    {'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()},
                    format='json',
                )
                return response.status_code, response.data
            finally:
                connection.close()

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(reserve, (buyer_one.id, buyer_two.id)))
            winners = sum(code in (200, 201) for code, _data in results)
            if winners != 1:
                raise CommandError(f'Concurrent reservation did not have one winner: {results}')
            created = list(BookReservation.objects.filter(
                book=book,
                status='PENDING',
            ))
            if len(created) != 1:
                raise CommandError('Concurrent reservation created duplicate pending rows.')
        finally:
            for reservation in BookReservation.objects.filter(
                book=book,
                status='PENDING',
            ):
                Notification.objects.filter(
                    entity_type='BOOK_RESERVATION',
                    entity_id=reservation.id,
                ).delete()
                reservation.delete()

        checkout_key = f'{FIXTURE_PREFIX}acceptance-concurrent-{uuid4().hex}'
        cart = Cart.objects.filter(user=buyer_one, status='ACTIVE').first()
        if cart is None or not cart.items.exists():
            raise CommandError('Active fixture cart with items required for checkout race test.')
        barrier = threading.Barrier(2)

        def checkout(_worker):
            close_old_connections()
            try:
                user = User.objects.get(pk=buyer_one.id)
                client = self.api_client(user)
                barrier.wait(timeout=20)
                response = client.post('/api/checkout/', {
                    'idempotency_key': checkout_key,
                    'shipping_address_snapshot': {
                        'recipient_name': buyer_one.full_name,
                        'phone': buyer_one.phone,
                        'address_line': 'Synthetic concurrency address',
                    },
                }, format='json')
                return response.status_code, response.data
            finally:
                connection.close()

        group = None
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                checkout_results = list(pool.map(checkout, (1, 2)))
            if any(code not in (200, 201) for code, _data in checkout_results):
                raise CommandError(f'Concurrent checkout failed: {checkout_results}')
            if checkout_results[0][1]['id'] != checkout_results[1][1]['id']:
                raise CommandError('Concurrent checkout returned different checkout groups.')
            group = CheckoutGroup.objects.get(
                buyer=buyer_one,
                idempotency_key=checkout_key,
            )
            if group.orders.count() != len(checkout_results[0][1]['orders']):
                raise CommandError('Concurrent checkout generated inconsistent orders.')
            if CheckoutGroup.objects.filter(
                buyer=buyer_one,
                idempotency_key=checkout_key,
            ).count() != 1:
                raise CommandError('Concurrent checkout created duplicate groups.')
        finally:
            if group is not None:
                with transaction.atomic():
                    for order in group.orders.all():
                        for item in order.sale_items.select_related('sale_listing', 'book'):
                            SaleListing.objects.filter(
                                pk=item.sale_listing_id,
                                status='RESERVED',
                            ).update(status='ACTIVE')
                            Book.objects.filter(
                                pk=item.book_id,
                                status='RESERVED',
                            ).update(status='AVAILABLE')
                        SaleOrderItem.objects.filter(order=order).delete()
                    group.orders.all().delete()
                    group.delete()
                    Cart.objects.filter(pk=cart.pk).update(status='ACTIVE')

        order = Order.objects.get(order_code='ORD-acceptance-fixture-1')
        payment_key = f'{FIXTURE_PREFIX}acceptance-payment-race-{uuid4().hex}'
        barrier = threading.Barrier(2)

        def create_payment(_worker):
            close_old_connections()
            try:
                user = User.objects.get(pk=buyer_one.id)
                client = self.api_client(user)
                barrier.wait(timeout=20)
                response = client.post(
                    f'/api/orders/{order.id}/payments/',
                    {
                        'provider': 'fake',
                        'payment_method': 'TEST',
                        'idempotency_key': payment_key,
                    },
                    format='json',
                )
                return response.status_code, response.data
            finally:
                connection.close()

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                payment_results = list(pool.map(create_payment, (1, 2)))
            if any(code not in (200, 201) for code, _data in payment_results):
                raise CommandError(f'Concurrent payment retry failed: {payment_results}')
            if payment_results[0][1]['id'] != payment_results[1][1]['id']:
                raise CommandError('Concurrent payment created multiple intents.')
            if Payment.objects.filter(
                provider='fake',
                idempotency_key=payment_key,
            ).count() != 1:
                raise CommandError('Concurrent payment intent was duplicated.')
        finally:
            Payment.objects.filter(provider='fake', idempotency_key=payment_key).delete()
        self.stdout.write('CONCURRENCY PASS: two-user reservation race, duplicate checkout, and duplicate payment intent.')

    def run_admin_probes(self):
        AuthUser = get_user_model()
        auth_admin, _created = AuthUser.objects.get_or_create(
            username='acceptance-admin',
            defaults={
                'email': 'acceptance-admin@example.invalid',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        auth_admin.is_staff = True
        auth_admin.is_superuser = True
        auth_admin.is_active = True
        auth_admin.set_password('AcceptanceOnly-Admin-42!')
        auth_admin.save()
        client = Client()
        if not client.login(
            username='acceptance-admin',
            password='AcceptanceOnly-Admin-42!',
        ):
            raise CommandError('Django Admin login failed.')

        model_list = [
            model for model in admin.site._registry
            if model._meta.db_table in LITE_TABLES
        ]
        admin_tables = {model._meta.db_table for model in model_list}
        if admin_tables != LITE_TABLES or len(model_list) != 41:
            raise CommandError(
                f'Admin registration incomplete: missing {sorted(LITE_TABLES - admin_tables)}',
            )
        admin_request = RequestFactory().get('/admin/')
        admin_request.user = auth_admin
        for model in model_list:
            model_admin = admin.site._registry[model]
            response = client.get(reverse(
                f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist',
            ))
            self.assert_status(response, 200, f'admin changelist {model._meta.db_table}')
            if model_admin.has_add_permission(admin_request):
                self.assert_status(
                    client.get(reverse(
                        f'admin:{model._meta.app_label}_{model._meta.model_name}_add',
                    )),
                    200,
                    f'admin add form {model._meta.db_table}',
                )
            obj = model._default_manager.order_by('pk').first()
            if obj is None:
                continue
            if model_admin.has_change_permission(admin_request, obj):
                if isinstance(model_admin, CompositeKeyAdmin):
                    object_id = ':'.join(
                        str(getattr(obj, model._meta.get_field(name).attname))
                        for name in model_admin.composite_key_fields
                    )
                else:
                    object_id = obj.pk
                self.assert_status(
                    client.get(reverse(
                        f'admin:{model._meta.app_label}_{model._meta.model_name}_change',
                        args=[object_id],
                    )),
                    200,
                    f'admin change form {model._meta.db_table}',
                )
            if model_admin.has_delete_permission(admin_request, obj):
                if isinstance(model_admin, CompositeKeyAdmin):
                    delete_url = reverse(
                        f'admin:{model._meta.app_label}_{model._meta.model_name}_composite_delete',
                        args=[object_id],
                    )
                else:
                    delete_url = reverse(
                        f'admin:{model._meta.app_label}_{model._meta.model_name}_delete',
                        args=[obj.pk],
                    )
                self.assert_status(
                    client.get(delete_url),
                    200,
                    f'admin delete confirmation {model._meta.db_table}',
                )
        self.assert_status(
            client.get('/admin/users/user/?q=acceptance-fixture&role__exact=STUDENT'),
            200,
            'admin user search and role filter',
        )
        self.assert_status(
            client.get('/admin/users/otpverification/?q=acceptance-fixture'),
            200,
            'admin OTP search',
        )

        with transaction.atomic():
            try:
                now = timezone.localtime()
                pending_listing = SaleListing.objects.filter(
                    title__startswith=FIXTURE_PREFIX,
                    status='PENDING',
                ).first()
                rejected_listing = SaleListing.objects.filter(
                    title__startswith=FIXTURE_PREFIX,
                    status='REJECTED',
                ).first()
                if pending_listing is None or rejected_listing is None:
                    raise CommandError('Pending/rejected listing fixtures are required.')
                listing_admin_url = reverse('admin:books_salelisting_changelist')
                approved = client.post(listing_admin_url, {
                    'action': 'approve_pending',
                    '_selected_action': [pending_listing.id],
                })
                self.assert_status(approved, 302, 'admin approve pending listing')
                pending_listing.refresh_from_db()
                if pending_listing.status != 'ACTIVE' or pending_listing.published_at is None:
                    raise CommandError('Admin approval did not publish the listing.')
                SaleListing.objects.filter(pk=rejected_listing.pk).update(status='PENDING')
                rejected = client.post(listing_admin_url, {
                    'action': 'reject_pending',
                    '_selected_action': [rejected_listing.id],
                })
                self.assert_status(rejected, 302, 'admin reject pending listing')
                rejected_listing.refresh_from_db()
                if rejected_listing.status != 'REJECTED':
                    raise CommandError('Admin rejection did not persist.')

                code = f'acc-admin-{uuid4().hex[:16]}'
                form_data = {
                    'name': 'Acceptance Admin CRUD',
                    'code': code,
                    'description': 'Synthetic admin acceptance operation',
                    'credits': '3',
                    'status': 'ACTIVE',
                    'created_at_0': now.strftime('%Y-%m-%d'),
                    'created_at_1': now.strftime('%H:%M:%S'),
                    'updated_at_0': now.strftime('%Y-%m-%d'),
                    'updated_at_1': now.strftime('%H:%M:%S'),
                }
                created = client.post(reverse('admin:users_subject_add'), form_data)
                self.assert_status(created, 302, 'admin add subject')
                subject = apps.get_model('users', 'Subject').objects.get(code=code)
                form_data.update({'name': 'Acceptance Admin Edited', 'credits': '4'})
                changed = client.post(
                    reverse('admin:users_subject_change', args=[subject.id]),
                    form_data,
                )
                self.assert_status(changed, 302, 'admin edit subject')
                subject.refresh_from_db()
                if subject.name != 'Acceptance Admin Edited' or subject.credits != 4:
                    raise CommandError('Django Admin edit did not persist.')
                deleted = client.post(
                    reverse('admin:users_subject_delete', args=[subject.id]),
                    {'post': 'yes'},
                )
                self.assert_status(deleted, 302, 'admin delete subject')
                if apps.get_model('users', 'Subject').objects.filter(pk=subject.id).exists():
                    raise CommandError('Django Admin delete did not remove the record.')

                BookWorkSubject = apps.get_model('books', 'BookWorkSubject')
                BookWork = apps.get_model('books', 'BookWork')
                work = BookWork.objects.order_by('id').first()
                linked_subject_ids = BookWorkSubject.objects.filter(
                    book_work=work,
                ).values_list('subject_id', flat=True)
                linked_subject_set = set(linked_subject_ids)
                linked_subject = apps.get_model('users', 'Subject').objects.exclude(
                    id__in=linked_subject_set,
                ).first()
                if work is None or linked_subject is None:
                    raise CommandError('Composite admin CRUD fixture records unavailable.')
                composite_id = f'{work.id}:{linked_subject.id}'
                composite_url = reverse(
                    'admin:books_bookworksubject_change',
                    args=[composite_id],
                )
                link_form = {
                    'book_work': work.id,
                    'subject': linked_subject.id,
                    'is_primary': '',
                    'created_at_0': now.strftime('%Y-%m-%d'),
                    'created_at_1': now.strftime('%H:%M:%S'),
                }
                self.assert_status(
                    client.post(reverse('admin:books_bookworksubject_add'), link_form),
                    302,
                    'admin add composite book subject',
                )
                link = BookWorkSubject.objects.get(
                    book_work=work,
                    subject=linked_subject,
                )
                self.assert_status(
                    client.post(
                        reverse('admin:books_bookworksubject_add'),
                        link_form,
                    ),
                    200,
                    'admin reject duplicate composite book subject',
                )
                if BookWorkSubject.objects.filter(
                    book_work=work,
                    subject=linked_subject,
                ).count() != 1:
                    raise CommandError('Admin duplicate composite key was not rejected.')
                self.assert_status(
                    client.post(
                        composite_url,
                        {
                            **link_form,
                            'created_at_1': (
                                now + timedelta(seconds=1)
                            ).strftime('%H:%M:%S'),
                        },
                    ),
                    302,
                    'admin edit composite book subject',
                )
                link = BookWorkSubject.objects.get(
                    book_work_id=work.id,
                    subject_id=linked_subject.id,
                )
                if link.is_primary or link.created_at == now:
                    raise CommandError('Composite Admin edit did not persist.')
                delete_url = reverse(
                    'admin:books_bookworksubject_composite_delete',
                    args=[composite_id],
                )
                self.assert_status(client.get(delete_url), 200, 'admin composite delete confirmation')
                self.assert_status(
                    client.post(delete_url, {'confirm': 'yes'}),
                    302,
                    'admin delete composite book subject',
                )
                if BookWorkSubject.objects.filter(
                    book_work=work,
                    subject=linked_subject,
                ).exists():
                    raise CommandError('Composite Admin delete did not remove the row.')

                ConversationMember = apps.get_model('messaging', 'ConversationMember')
                conversation = Conversation.objects.order_by('id').first()
                member_user = User.objects.exclude(
                    id__in=ConversationMember.objects.filter(
                        conversation=conversation,
                    ).values_list('user_id', flat=True),
                ).first()
                if conversation is None or member_user is None:
                    raise CommandError('Composite conversation member fixture unavailable.')
                membership_id = f'{conversation.id}:{member_user.id}'
                membership_form = {
                    'conversation': conversation.id,
                    'user': member_user.id,
                    'joined_at_0': now.strftime('%Y-%m-%d'),
                    'joined_at_1': now.strftime('%H:%M:%S'),
                    'last_read_at_0': '',
                    'last_read_at_1': '',
                }
                self.assert_status(
                    client.post(
                        reverse('admin:messaging_conversationmember_add'),
                        membership_form,
                    ),
                    302,
                    'admin add composite conversation member',
                )
                self.assert_status(
                    client.post(
                        reverse('admin:messaging_conversationmember_add'),
                        membership_form,
                    ),
                    200,
                    'admin reject duplicate conversation member',
                )
                if ConversationMember.objects.filter(
                    conversation=conversation,
                    user=member_user,
                ).count() != 1:
                    raise CommandError('Admin duplicate membership was not rejected.')
                self.assert_status(
                    client.post(
                        reverse(
                            'admin:messaging_conversationmember_change',
                            args=[membership_id],
                        ),
                        membership_form,
                    ),
                    302,
                    'admin edit composite conversation member',
                )
                membership_delete_url = reverse(
                    'admin:messaging_conversationmember_composite_delete',
                    args=[membership_id],
                )
                self.assert_status(
                    client.post(membership_delete_url, {'confirm': 'yes'}),
                    302,
                    'admin delete composite conversation member',
                )
                if ConversationMember.objects.filter(
                    conversation=conversation,
                    user=member_user,
                ).exists():
                    raise CommandError('Composite Admin delete did not remove membership.')
            finally:
                transaction.set_rollback(True)
        self.stdout.write(
            'ADMIN PASS: login, all 41 list/add/change/delete screens, search/filter, and CRUD including both composite-key tables.',
        )

    def run_performance_probes(self):
        buyer = User.objects.get(email=f'{FIXTURE_PREFIX}buyer_1@example.invalid')
        admin_user = User.objects.get(email=f'{FIXTURE_PREFIX}admin@example.invalid')
        book = Book.objects.filter(
            status='AVAILABLE',
            sale_listings__status='ACTIVE',
        ).first()
        conversation_id = ConversationMember.objects.filter(
            user=buyer,
        ).values_list('conversation_id', flat=True).first()
        client = self.api_client(buyer)
        admin_client = self.api_client(admin_user)
        probes = {
            'books_list': (client, '/api/books/?page=1&page_size=50'),
            'books_search': (
                client,
                '/api/books/?search=acceptance-fixture-book-0499&page=1&page_size=20',
            ),
            'books_filter_sort': (
                client,
                '/api/books/?condition_status=good&publication_year=2024&sort=price_asc&page=1&page_size=20',
            ),
            'book_detail': (client, f'/api/books/{book.id}/'),
            'favorites': (client, '/api/favorites/?page=1&page_size=20'),
            'orders': (client, '/api/orders/?page=1&page_size=20'),
            'messages': (
                client,
                f'/api/conversations/{conversation_id}/messages/?page=1&page_size=50',
            ),
            'dashboard': (admin_client, '/api/admin/dashboard/'),
        }
        measured = {}
        for name, (probe_client, path) in probes.items():
            started = time.perf_counter()
            with CaptureQueriesContext(connection) as queries:
                response = probe_client.get(path)
            elapsed_ms = (time.perf_counter() - started) * 1000
            self.assert_status(response, 200, f'performance {name}')
            measured[name] = (len(queries), elapsed_ms)
            if len(queries) > 15:
                raise CommandError(f'{name} used {len(queries)} SQL queries (limit 15).')
            if name == 'books_list':
                if response.data['count'] < 100 or len(response.data['results']) > 50:
                    raise CommandError('Book API is not paginating the large fixture dataset.')
            if name == 'dashboard' and 'shipments' not in response.data:
                raise CommandError('Dashboard shipment aggregate was not returned.')
        formatted = ', '.join(
            f'{name}={count}q/{elapsed:.1f}ms'
            for name, (count, elapsed) in measured.items()
        )
        self.stdout.write(f'PERFORMANCE PASS (500 books, max 15 SQL queries per endpoint): {formatted}')

    @staticmethod
    def expired_access_token(user):
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken.for_user(user)
        token['exp'] = int(time.time()) - 1
        return str(token)

    @staticmethod
    def otp_from_latest_email():
        if not mail.outbox:
            raise CommandError('OTP email was not delivered to the local test backend.')
        match = re.search(r'\b(\d{6})\b', mail.outbox[-1].body)
        if match is None:
            raise CommandError('OTP email did not contain a six-digit test code.')
        return match.group(1)

    @staticmethod
    def api_client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @staticmethod
    def assert_status(response, expected, label):
        expected_codes = (expected,) if isinstance(expected, int) else expected
        if response.status_code not in expected_codes:
            data = getattr(response, 'data', None)
            raise CommandError(
                f'{label} returned HTTP {response.status_code}, expected {expected_codes}: {data}',
            )

    @staticmethod
    def _local_email_settings():
        from django.test import override_settings

        return override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
            OTP_RESEND_COOLDOWN_SECONDS=0,
            OTP_MAX_ATTEMPTS=2,
            OTP_MAX_RESENDS=1,
        )
