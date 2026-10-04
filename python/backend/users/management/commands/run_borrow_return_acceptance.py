from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection
from django.utils import timezone
from rest_framework.test import APIClient

from books.models import BorrowOrder, Book, LendListing, Order, Payment, Shipment
from users.models import User


FIXTURE_PREFIX = 'borrow-return-acceptance-'
FIXTURE_PASSWORD = 'BorrowReturn-Acceptance-42!'


class Command(BaseCommand):
    help = 'Run authenticated API and real concurrent DB acceptance for book returns.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-local-test-db', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm local test DB use.')
        self._assert_local_test_database()
        lender, _lender_token = self._login('lender')
        borrower, borrower_token = self._login('borrower')
        outsider, _outsider_token = self._login('outsider')
        self._verify_fixture()
        self._verify_authorization(lender, borrower, outsider)
        self._verify_concurrent_duplicate_protection(borrower_token)
        self._verify_complete_return_flow(lender, borrower)
        self.stdout.write(self.style.SUCCESS(
            'BORROW RETURN LOCAL API/DB ACCEPTANCE: PASS',
        ))

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
            raise CommandError('Refusing acceptance outside the approved local Lite test DB.')
        if settings.PASSBOOK_ENVIRONMENT != 'test':
            raise CommandError('Run acceptance with PASSBOOK_ENVIRONMENT=test.')
        if not settings.PASSBOOK_FAKE_PAYMENTS_ENABLED:
            raise CommandError('Enable the local Fake Payment Provider for acceptance.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            if cursor.fetchone()[0] != expected['NAME']:
                raise CommandError('The active SQL database is not the approved local test DB.')

    @staticmethod
    def _login(role):
        email = f'{FIXTURE_PREFIX}{role}@example.invalid'
        client = APIClient(HTTP_HOST='localhost')
        response = client.post(
            '/api/auth/login/',
            {'email': email, 'password': FIXTURE_PASSWORD},
            format='json',
        )
        if response.status_code != 200 or not response.data.get('access'):
            raise CommandError(f'Acceptance login failed for synthetic {role} account.')
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return client, response.data['access']

    @staticmethod
    def _verify_fixture():
        borrows = list(
            BorrowOrder.objects.filter(
                order__order_code__startswith=FIXTURE_PREFIX,
            ).select_related(
                'order',
                'lend_listing',
                'lend_listing__book',
                'borrower',
                'lender',
            ).order_by('id'),
        )
        if len(borrows) != 2:
            raise CommandError('Create the two ACTIVE return fixtures before running acceptance.')
        if any(
            borrow.status != 'ACTIVE'
            or borrow.lend_listing.status != 'ON_LOAN'
            or borrow.lend_listing.book.status != 'ON_LOAN'
            or not borrow.order.shipments.filter(status='DELIVERED').exists()
            for borrow in borrows
        ):
            raise CommandError('Acceptance fixtures must start ACTIVE with outbound delivery.')

    def _verify_authorization(self, lender, borrower, outsider):
        browser_borrow = BorrowOrder.objects.get(
            order__order_code=f'{FIXTURE_PREFIX}browser-order',
        )
        payload = {
            'return_method': 'DELIVERY',
            'carrier': 'Acceptance carrier',
            'return_tracking_code': f'{FIXTURE_PREFIX}auth-attempt',
        }
        for role_client, role in ((lender, 'lender'), (outsider, 'outsider')):
            response = role_client.post(
                f'/api/borrow-orders/{browser_borrow.id}/return-request/',
                payload,
                format='json',
            )
            if response.status_code != 403:
                raise CommandError(f'{role} return request was not rejected with 403.')
        response = borrower.post(
            f'/api/borrow-orders/{browser_borrow.id}/complete/',
            {},
            format='json',
        )
        if response.status_code != 403:
            raise CommandError('Borrower was not rejected when trying to confirm receipt.')
        browser_borrow.refresh_from_db()
        if browser_borrow.status != 'ACTIVE':
            raise CommandError('Unauthorized return attempts changed the active fixture.')

    @staticmethod
    def _post_concurrently(access_token, borrow_id):
        barrier = Barrier(2)

        def send_request(suffix):
            close_old_connections()
            try:
                client = APIClient(HTTP_HOST='localhost')
                client.credentials(
                    HTTP_AUTHORIZATION=f'Bearer {access_token}',
                )
                barrier.wait(timeout=10)
                response = client.post(
                    f'/api/borrow-orders/{borrow_id}/return-request/',
                    {
                        'return_method': 'DELIVERY',
                        'carrier': 'Acceptance concurrent carrier',
                        'return_tracking_code': f'{FIXTURE_PREFIX}concurrent-{suffix}',
                    },
                    format='json',
                )
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(send_request, 'A'),
                executor.submit(send_request, 'B'),
            ]
            return [future.result(timeout=30) for future in futures]

    def _verify_concurrent_duplicate_protection(self, borrower_token):
        borrow = BorrowOrder.objects.select_related('order').get(
            order__order_code=f'{FIXTURE_PREFIX}concurrency-order',
        )
        outcomes = self._post_concurrently(
            borrower_token,
            borrow.id,
        )
        statuses = sorted(status_code for status_code, _data in outcomes)
        if statuses != [201, 400]:
            raise CommandError(
                f'Concurrent return requests expected [201, 400], got {statuses}.',
            )
        borrow.refresh_from_db()
        if borrow.status != 'RETURN_REQUESTED' or borrow.return_status != 'SHIPPING':
            raise CommandError('Concurrent request did not leave exactly one active Return Request.')
        return_shipment = Shipment.objects.filter(
            order=borrow.order,
            tracking_code=borrow.return_tracking_code,
        )
        if return_shipment.count() != 1:
            raise CommandError('Concurrent request created an unexpected number of shipments.')
        if Shipment.objects.filter(
            order=borrow.order,
            tracking_code__startswith=f'{FIXTURE_PREFIX}concurrent-',
        ).count() != 1:
            raise CommandError('A duplicate concurrent return shipment was persisted.')
        retry_response = APIClient(HTTP_HOST='localhost')
        retry_response.credentials(HTTP_AUTHORIZATION=f'Bearer {borrower_token}')
        repeated = retry_response.post(
            f'/api/borrow-orders/{borrow.id}/return-request/',
            {
                'return_method': 'DELIVERY',
                'carrier': 'Acceptance concurrent carrier',
                'return_tracking_code': borrow.return_tracking_code,
            },
            format='json',
        )
        if repeated.status_code != 400 or return_shipment.count() != 1:
            raise CommandError('A retried Return Request created a duplicate shipment.')
        if Order.objects.filter(pk=borrow.order_id).exclude(order_type='BORROW').exists():
            raise CommandError('Return incorrectly created or changed the order type.')
        if Payment.objects.filter(order_id=borrow.order_id).exists():
            raise CommandError('Return flow unexpectedly created a payment.')
        self.stdout.write('DB concurrency PASS: 2 simultaneous requests → 1 created, 1 rejected.')

    def _verify_complete_return_flow(self, lender, borrower):
        borrow = BorrowOrder.objects.select_related(
            'order',
            'lend_listing__book',
        ).get(order__order_code=f'{FIXTURE_PREFIX}concurrency-order')
        shipment = Shipment.objects.get(
            order=borrow.order,
            tracking_code=borrow.return_tracking_code,
        )
        if shipment.status != 'PENDING':
            raise CommandError('Return shipment did not start in PENDING.')
        response = borrower.get('/api/borrow-orders/')
        payload = next(
            (row for row in response.data['results'] if row['id'] == borrow.id),
            None,
        )
        if response.status_code != 200 or not payload:
            raise CommandError('Borrower cannot read their return shipment details.')
        if (
            payload.get('return_shipment', {}).get('direction')
            != 'BORROWER_TO_OWNER'
        ):
            raise CommandError('Return Shipment direction is not BORROWER_TO_OWNER.')

        for tracking_status in ('PICKED_UP', 'IN_TRANSIT', 'DELIVERED'):
            tracking = borrower.post(
                f'/api/shipments/{shipment.id}/tracking/',
                {'status': tracking_status},
                format='json',
            )
            if tracking.status_code != 201:
                raise CommandError(
                    f'Return shipment tracking {tracking_status} failed.',
                )
            shipment.refresh_from_db()
            borrow.refresh_from_db()
            borrow.lend_listing.refresh_from_db()
            borrow.lend_listing.book.refresh_from_db()
            if shipment.status != tracking_status:
                raise CommandError(f'Database did not persist {tracking_status}.')
            expected_borrow_status = (
                'RETURNED' if tracking_status == 'DELIVERED' else 'RETURN_REQUESTED'
            )
            if borrow.status != expected_borrow_status:
                raise CommandError(
                    f'Borrow status should be {expected_borrow_status} after {tracking_status}.',
                )
            if tracking_status != 'DELIVERED' and (
                borrow.lend_listing.book.status != 'ON_LOAN'
                or borrow.lend_listing.status != 'ON_LOAN'
            ):
                raise CommandError('Inventory reopened before lender confirmation.')

        rejected = borrower.post(
            f'/api/borrow-orders/{borrow.id}/complete/',
            {},
            format='json',
        )
        if rejected.status_code != 403:
            raise CommandError('Borrower could confirm a delivered return.')

        completed = lender.post(
            f'/api/borrow-orders/{borrow.id}/complete/',
            {},
            format='json',
        )
        if completed.status_code != 200:
            raise CommandError('Lender could not confirm the delivered return.')
        borrow.refresh_from_db()
        borrow.order.refresh_from_db()
        borrow.lend_listing.refresh_from_db()
        borrow.lend_listing.book.refresh_from_db()
        shipment.refresh_from_db()
        if not (
            borrow.status == 'COMPLETED'
            and borrow.return_status == 'COMPLETED'
            and borrow.order.status == 'COMPLETED'
            and shipment.status == 'DELIVERED'
            and borrow.lend_listing.status == 'ACTIVE'
            and borrow.lend_listing.book.status == 'AVAILABLE'
        ):
            raise CommandError('Final Borrow/Book/Listing DB state is inconsistent.')
        if borrow.actual_return_at is None or borrow.return_approved_at is None:
            raise CommandError('Return confirmation timestamps were not persisted.')
        if Payment.objects.filter(order_id=borrow.order_id).exists():
            raise CommandError('Return completion unexpectedly created a payment.')
        self.stdout.write(
            'DB state PASS: RETURN_REQUESTED → SHIPPING → DELIVERED/RETURNED '
            '→ lender confirmed → COMPLETED/AVAILABLE.',
        )
