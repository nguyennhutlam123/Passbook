import re
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from config.composite_admin import CompositeKeyAdmin
from .models import Book, BookReservation, BorrowOrder, Payment
from .serializers import (
    BookSerializer,
    BookListSerializer,
    BookWriteSerializer,
    FavoriteBookSerializer,
)
from .services import (
    FakePaymentProvider,
    PaymentProviderUnavailable,
    calculate_payment_split,
    get_payment_provider,
    transition_fake_payment,
    transition_fake_refund,
    transition_borrow_order,
    transition_reservation,
)
from .sale_api_views import SaleListingDetailView, SaleListingInputSerializer
from .commerce_api_views import (
    BookReservationListCreateView,
    CartItemInputSerializer,
    CheckoutView,
    FakePaymentTransitionView,
    OrderDetailView,
    PaymentInputSerializer,
    PaymentListCreateView,
    RefundCreateView,
    ReturnActionView,
    CheckoutAddressInputSerializer,
    CheckoutInputSerializer,
    lend_listing_payload,
)
from .api_views import BookDetailView
from .request_api_views import BookIntentSummaryView, BookRequestDetailView
from users.models import OtpVerification


class LiteModelMappingTests(SimpleTestCase):
    def test_models_cover_lite_tables_and_columns(self):
        ddl_path = settings.BASE_DIR.parent.parent / 'docs/database/passbook_v1.2_lite.sql'
        ddl = ddl_path.read_text()
        expected = {}
        for table, body in re.findall(
            r'CREATE TABLE `([^`]+)` \(\n(.*?)\n\) ENGINE=',
            ddl,
            re.S,
        ):
            columns = set()
            nullable_columns = {}
            for line in body.splitlines():
                match = re.match(r'  `([^`]+)` (.*?)(?:,)?$', line)
                if match and 'GENERATED ALWAYS' not in match.group(2):
                    column, definition = match.groups()
                    columns.add(column)
                    nullable_columns[column] = bool(
                        re.search(r'\bNULL\b', definition)
                        and not re.search(r'\bNOT NULL\b', definition)
                    )
            foreign_keys = [
                (
                    re.findall(r'`([^`]+)`', local),
                    target_table,
                    re.findall(r'`([^`]+)`', remote),
                )
                for local, target_table, remote in re.findall(
                    r'FOREIGN KEY \(([^)]+)\) REFERENCES `([^`]+)` \(([^)]+)\)',
                    body,
                )
            ]
            primary_key = re.search(r'PRIMARY KEY \(([^)]+)\)', body)
            primary_key_columns = (
                re.findall(r'`([^`]+)`', primary_key.group(1))
                if primary_key
                else []
            )
            expected[table] = (
                columns,
                nullable_columns,
                foreign_keys,
                primary_key_columns,
            )

        models = {
            model._meta.db_table: model
            for model in apps.get_models()
            if model._meta.app_label in {
                'users', 'books', 'messaging', 'notifications', 'reports',
            }
        }
        self.assertEqual(len(expected), 41)
        self.assertEqual(set(models), set(expected))
        composite_primary_key_tables = {
            'book_work_subjects',
            'conversation_members',
        }
        self.assertEqual(
            {
                table
                for table, (_columns, _nullable, _foreign_keys, primary_key) in expected.items()
                if len(primary_key) > 1
            },
            composite_primary_key_tables,
        )
        for table, (
            columns,
            nullable_columns,
            foreign_keys,
            primary_key_columns,
        ) in expected.items():
            model = models[table]
            self.assertFalse(model._meta.managed, table)
            mapped_fields = {
                field.column: field for field in model._meta.concrete_fields
            }
            mapped_columns = set(mapped_fields)
            self.assertEqual(mapped_columns, columns, table)
            for column, nullable in nullable_columns.items():
                self.assertEqual(mapped_fields[column].null, nullable, f'{table}.{column}')
            if table not in composite_primary_key_tables:
                self.assertEqual(model._meta.pk.column, primary_key_columns[0], table)
            expected_relations = {}
            for local_columns, target_table, target_columns in foreign_keys:
                self.assertEqual(len(local_columns), len(target_columns), table)
                for local_column, target_column in zip(local_columns, target_columns):
                    expected_relations.setdefault(local_column, set()).add(
                        (target_table, target_column),
                    )
            for local_column, targets in expected_relations.items():
                field = next(
                    item for item in model._meta.concrete_fields
                    if item.column == local_column
                )
                self.assertTrue(field.is_relation, (table, local_column))
                self.assertIn(
                    (
                        field.remote_field.model._meta.db_table,
                        field.target_field.column,
                    ),
                    targets,
                    (table, local_column),
                )

    def test_ddl_enum_values_match_model_choices(self):
        ddl_path = settings.BASE_DIR.parent.parent / 'docs/database/passbook_v1.2_lite.sql'
        ddl = ddl_path.read_text()
        models = {
            model._meta.db_table: model
            for model in apps.get_models()
            if model._meta.app_label in {
                'users', 'books', 'messaging', 'notifications', 'reports',
            }
        }
        enum_count = 0
        for table, body in re.findall(
            r'CREATE TABLE `([^`]+)` \(\n(.*?)\n\) ENGINE=',
            ddl,
            re.S,
        ):
            fields = {
                field.column: field
                for field in models[table]._meta.concrete_fields
            }
            for column, definition in re.findall(
                r"  `([^`]+)` (ENUM\([^)]*\)[^,]*)",
                body,
            ):
                enum_count += 1
                ddl_values = set(re.findall(r"'([^']*)'", definition))
                model_values = {
                    value for value, _label in fields[column].choices
                }
                self.assertEqual(model_values, ddl_values, f'{table}.{column}')
        self.assertEqual(enum_count, 3)

    def test_lite_ddl_is_41_tables_with_safe_otp_constraints(self):
        ddl_path = settings.BASE_DIR.parent.parent / 'docs/database/passbook_v1.2_lite.sql'
        ddl = ddl_path.read_text()
        tables = re.findall(r'CREATE TABLE `([^`]+)`', ddl)
        self.assertEqual(len(tables), 41)
        self.assertEqual(len(set(tables)), 41)
        self.assertEqual(tables.count('otp_verifications'), 1)
        otp_table = re.search(
            r'CREATE TABLE `otp_verifications` \((.*?)\) ENGINE=',
            ddl,
            re.S,
        ).group(1)
        for required_index in (
            'idx_otp_target_purpose_status',
            'idx_otp_user_purpose_status',
            'idx_otp_expires_at',
        ):
            self.assertIn(required_index, otp_table)
        self.assertRegex(
            otp_table,
            r'FOREIGN KEY \(`user_id`\) REFERENCES `users` \(`id`\)'
            r' ON DELETE SET NULL ON UPDATE CASCADE',
        )
        self.assertNotRegex(ddl, r'\b(?:CREATE|DROP)\s+DATABASE\b')
        self.assertNotRegex(ddl, r'\b(?:FLOAT|DOUBLE)\b')
        self.assertNotIn('utf8mb4_0900_ai_ci', ddl)

    def test_lifecycle_models_remain_distinct(self):
        self.assertEqual(BookReservation._meta.db_table, 'book_reservations')
        self.assertEqual(BorrowOrder._meta.db_table, 'borrow_orders')
        self.assertEqual(Book._meta.db_table, 'books')
        self.assertEqual(
            {
                BookReservation._meta.get_field('status').choices[index][0]
                for index in range(len(BookReservation._meta.get_field('status').choices))
            },
            {'PENDING', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'COMPLETED'},
        )
        borrow_fields = {
            'expected_start_at', 'expected_return_at',
            'actual_start_at', 'actual_return_at',
        }
        self.assertTrue(
            borrow_fields <= {field.name for field in BorrowOrder._meta.fields},
        )


class PaymentFeeTests(SimpleTestCase):
    def test_fee_split_uses_vnd_precision(self):
        result = calculate_payment_split('100000', '0.05')
        self.assertEqual(result['amount'], 100000)
        self.assertEqual(result['platform_fee'], 5000)
        self.assertEqual(result['seller_amount'], 95000)

    def test_fee_rate_must_be_between_zero_and_one(self):
        for rate in ('-0.01', '1.01'):
            with self.subTest(rate=rate):
                with self.assertRaises(ValidationError):
                    calculate_payment_split('100000', rate)


class FavoritePayloadTests(SimpleTestCase):
    def test_favorite_book_uses_the_compact_card_payload(self):
        self.assertEqual(
            set(FavoriteBookSerializer().fields),
            set(BookListSerializer().fields),
        )
        self.assertNotIn('description', FavoriteBookSerializer().fields)
        self.assertNotIn('images', FavoriteBookSerializer().fields)


class LegacyBookInputCompatibilityTests(SimpleTestCase):
    def test_pickup_location_is_rejected_explicitly(self):
        serializer = BookWriteSerializer(data={
            'title': 'Test book',
            'price': '100000.0000',
            'condition_status': 'good',
            'pickup_location_id': 12,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('pickup_location_id', serializer.errors)

    def test_legacy_book_input_defaults_to_buy_and_still_requires_price(self):
        serializer = BookWriteSerializer(data={
            'title': 'Legacy listing',
            'price': '100000',
            'condition_status': 'good',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['listing_type'], 'BUY')

    def test_borrow_listing_requires_existing_borrow_terms_without_sale_price(self):
        serializer = BookWriteSerializer(data={
            'listing_type': 'BORROW',
            'title': 'Borrow listing',
            'rental_fee': '0',
            'condition_status': 'good',
            'max_days': 14,
            'shipping_paid_by': 'BORROWER',
            'return_method': 'IN_PERSON',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

        invalid = BookWriteSerializer(data={
            'listing_type': 'BORROW',
            'title': 'Borrow listing',
            'price': '100000',
            'rental_fee': '0',
            'condition_status': 'good',
            'max_days': 14,
            'shipping_paid_by': 'BORROWER',
            'return_method': 'IN_PERSON',
        })
        self.assertFalse(invalid.is_valid())
        self.assertIn('price', invalid.errors)

    def test_borrow_listing_requires_terms_fields_supported_by_lite_schema(self):
        serializer = BookWriteSerializer(data={
            'listing_type': 'BORROW',
            'title': 'Borrow listing',
            'rental_fee': '0',
            'condition_status': 'good',
        })
        self.assertFalse(serializer.is_valid())
        for field in ('max_days', 'shipping_paid_by', 'return_method'):
            self.assertIn(field, serializer.errors)


class BuyBorrowSeparationTests(SimpleTestCase):
    def test_cart_rejects_borrow_listing_type(self):
        serializer = CartItemInputSerializer(data={
            'listing_type': 'BORROW',
            'listing_id': 12,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('listing_type', serializer.errors)

    def test_checkout_rejects_borrow_without_creating_an_order(self):
        item = SimpleNamespace(sale_listing_id=None, lend_listing_id=12)
        with self.assertRaises(ValidationError):
            CheckoutView._checkout_line(item, SimpleNamespace(id=8))


class ReservationApiValidationTests(SimpleTestCase):
    def test_duplicate_active_reservation_returns_a_validation_error(self):
        expires_at = (timezone.now() + timedelta(hours=1)).isoformat()
        request = APIRequestFactory().post(
            '/api/books/6/reservations/',
            {'expires_at': expires_at},
            format='json',
        )
        request.data = {'expires_at': expires_at}
        request.user = SimpleNamespace(id=8, is_authenticated=True)
        book = SimpleNamespace(owner_id=7, status='RESERVED')
        book_manager = Mock()
        reservations_manager = Mock()
        reservations_manager.filter.return_value.exists.return_value = True

        with patch('books.commerce_api_views.get_object_or_404', return_value=book), patch(
            'books.commerce_api_views.Book.objects',
            book_manager,
        ), patch(
            'books.commerce_api_views.BookReservation.objects',
            reservations_manager,
        ):
            with self.assertRaisesMessage(
                ValidationError,
                'Sách đã có một yêu cầu đặt còn hiệu lực.',
            ):
                BookReservationListCreateView.post.__wrapped__(
                    BookReservationListCreateView(),
                    request,
                    book_id=6,
                )


class BookListPayloadTests(SimpleTestCase):
    def test_list_serializer_excludes_detail_and_relationship_payloads(self):
        self.assertEqual(
            set(BookListSerializer().fields),
            {
                'id',
                'title',
                'price',
                'condition_status',
                'condition_label',
                'publication_year',
                'edition',
                'primary_image',
                'subject',
                'category',
                'seller',
                'buying_intent_count',
                'selling_intent_count',
            },
        )
        self.assertEqual(
            BookListSerializer().fields['edition'].source,
            'book_edition.edition_name',
        )


class BookStatusSerializationTests(SimpleTestCase):
    def test_borrowed_book_is_not_reported_as_available(self):
        book = SimpleNamespace(
            status='ON_LOAN',
            _active_sale_listing=lambda: None,
            _active_lend_listing=lambda: SimpleNamespace(status='ON_LOAN'),
        )

        self.assertEqual(BookSerializer.get_status(book), 'on_loan')


class BookIntentEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_intent_summary_is_public_and_returns_aggregates(self):
        request = self.factory.get('/api/books/12/intents/')
        with patch('books.request_api_views.get_object_or_404', return_value=object()), patch(
            'books.request_api_views.intent_summary',
            return_value={
                'buying_count': 3,
                'selling_count': 1,
                'my_buy_request_id': None,
                'my_sell_intent_request_id': None,
            },
        ):
            response = BookIntentSummaryView.as_view()(request, book_id=12)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['buying_count'], 3)
        self.assertNotIn('users', response.data)

    def test_intent_changes_require_authentication(self):
        request = self.factory.post(
            '/api/books/12/intents/',
            {'request_type': 'BUY'},
            format='json',
        )
        response = BookIntentSummaryView.as_view()(request, book_id=12)
        self.assertEqual(response.status_code, 401)

    def test_intent_changes_reject_unsupported_types(self):
        request = self.factory.post(
            '/api/books/12/intents/',
            {'request_type': 'FAVORITE'},
            format='json',
        )
        user = SimpleNamespace(id=5, is_authenticated=True)
        force_authenticate(request, user=user)
        response = BookIntentSummaryView.as_view()(request, book_id=12)
        self.assertEqual(response.status_code, 400)


class LendListingPayloadTests(SimpleTestCase):
    def test_catalog_payload_contains_book_context_and_primary_image(self):
        subject = SimpleNamespace(id=5, name='Physics', code='PHY101')
        category = SimpleNamespace(name='Textbooks')
        image = SimpleNamespace(
            id=8,
            image_url='https://images.example.invalid/book.jpg',
            is_primary=True,
        )
        work = SimpleNamespace(
            id=44,
            author_name='A. Author',
            category_id=9,
            category=category,
            primary_subject_links=[SimpleNamespace(subject=subject)],
        )
        edition = SimpleNamespace(
            book_work=work,
            edition_name='Second edition',
            edition_number=2,
            publication_year=2024,
            publisher_name='Example Press',
            language=SimpleNamespace(id=1, name='English', code='en'),
        )
        book = SimpleNamespace(
            id=12,
            book_edition=edition,
            condition_status='good',
            condition_label='GOOD',
            condition_description='Lightly used',
            catalog_images=[image],
        )
        listing = SimpleNamespace(
            id=17,
            book_id=12,
            lender_id=3,
            lender=SimpleNamespace(
                full_name='Lender',
                university_id=6,
                university=SimpleNamespace(name='Example University'),
            ),
            book=book,
            title='Borrowable textbook',
            description='Borrow details',
            status='ACTIVE',
            deposit_amount=None,
            rental_fee=Decimal('25000.0000'),
            currency='VND',
            created_at=timezone.now(),
            buying_intent_count=4,
            selling_intent_count=1,
        )
        payload = lend_listing_payload(listing)
        self.assertEqual(payload['primary_image'], image.image_url)
        self.assertEqual(payload['condition_status'], 'good')
        self.assertEqual(payload['subject']['code'], 'PHY101')
        self.assertEqual(
            payload['book']['seller']['university']['name'],
            'Example University',
        )
        self.assertEqual(payload['buying_intent_count'], 4)


class AdminCoverageTests(SimpleTestCase):
    def test_every_lite_model_is_registered_in_admin(self):
        app_labels = {
            'users', 'books', 'messaging', 'notifications', 'reports',
        }
        model_tables = {
            model._meta.db_table
            for model in apps.get_models()
            if model._meta.app_label in app_labels
        }
        admin_tables = {
            model._meta.db_table
            for model in admin.site._registry
            if model._meta.app_label in app_labels
        }
        self.assertEqual(model_tables, admin_tables)

    def test_composite_key_admin_models_support_row_safe_crud(self):
        composite_key_models = (
            apps.get_model('books', 'BookWorkSubject'),
            apps.get_model('messaging', 'ConversationMember'),
        )
        request = SimpleNamespace(
            user=SimpleNamespace(has_perm=lambda _permission: True),
        )
        for model in composite_key_models:
            model_admin = admin.site._registry[model]
            self.assertIsInstance(model_admin, CompositeKeyAdmin)
            self.assertTrue(model_admin.has_add_permission(request))
            self.assertTrue(model_admin.has_change_permission(request))
            self.assertTrue(model_admin.has_delete_permission(request))
            self.assertEqual(len(model_admin.composite_key_fields), 2)

    def test_otp_admin_never_displays_hash(self):
        otp_admin = admin.site._registry[OtpVerification]
        self.assertNotIn('otp_hash', otp_admin.list_display)
        self.assertNotIn('otp_hash', otp_admin.fields)


class PolymorphicValidationTests(SimpleTestCase):
    def test_refund_requires_exactly_one_target(self):
        from .commerce_api_views import RefundInputSerializer

        serializer = RefundInputSerializer(data={
            'payment_id': 1,
            'idempotency_key': 'test-refund',
            'reason': 'test',
            'amount': '10.0000',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)


class SaleListingPermissionTests(SimpleTestCase):
    def test_user_cannot_patch_or_delete_another_users_listing(self):
        factory = APIRequestFactory()
        outsider = SimpleNamespace(id=99, is_authenticated=True)
        listing = SimpleNamespace(
            id=44,
            seller_id=7,
            status='ACTIVE',
            save=Mock(),
        )
        for method in ('patch', 'delete'):
            with self.subTest(method=method):
                request = (
                    factory.patch('/api/sale-listings/44/', {'price': '10'})
                    if method == 'patch'
                    else factory.delete('/api/sale-listings/44/')
                )
                request.user = outsider
                request.data = {'price': '10'}
                view_method = getattr(SaleListingDetailView, method)
                with patch(
                    'books.sale_api_views.get_object_or_404',
                    return_value=listing,
                ):
                    with self.assertRaises(PermissionDenied):
                        view_method.__wrapped__(
                            SaleListingDetailView(),
                            request,
                            listing_id=44,
                        )
                self.assertEqual(listing.status, 'ACTIVE')
                listing.save.assert_not_called()

    def test_owner_can_manage_own_listing(self):
        request = SimpleNamespace(user=SimpleNamespace(id=7))
        listing = SimpleNamespace(seller_id=7, status='ACTIVE')
        SaleListingDetailView._require_owner(request, listing)
        SaleListingDetailView._require_editable(listing)

    def test_other_seller_cannot_manage_listing(self):
        request = SimpleNamespace(user=SimpleNamespace(id=8))
        listing = SimpleNamespace(seller_id=7, status='ACTIVE')
        with self.assertRaises(PermissionDenied):
            SaleListingDetailView._require_owner(request, listing)

    def test_reserved_or_sold_listing_cannot_be_edited(self):
        for listing_status in ('RESERVED', 'SOLD'):
            with self.subTest(status=listing_status):
                with self.assertRaises(ValidationError):
                    SaleListingDetailView._require_editable(
                        SimpleNamespace(status=listing_status),
                    )


class BookOwnershipEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(id=10, is_authenticated=True)
        self.other_owner_book = SimpleNamespace(
            id=32,
            owner_id=20,
            status='AVAILABLE',
            save=Mock(),
        )

    def test_user_cannot_patch_or_delete_another_users_book(self):
        for method in ('patch', 'delete'):
            with self.subTest(method=method):
                request = (
                    self.factory.patch('/api/books/32/', {'title': 'Changed'})
                    if method == 'patch'
                    else self.factory.delete('/api/books/32/')
                )
                force_authenticate(request, user=self.user)
                with patch(
                    'books.api_views.get_object_or_404',
                    return_value=self.other_owner_book,
                ) as get_book:
                    response = BookDetailView.as_view()(request, pk=32)

                self.assertEqual(response.status_code, 403)
                get_book.assert_called_once_with(Book, pk=32)
                self.assertEqual(self.other_owner_book.status, 'AVAILABLE')
                self.other_owner_book.save.assert_not_called()


class SaleListingInputTests(SimpleTestCase):
    def test_client_cannot_choose_moderation_or_marketplace_status(self):
        for unsafe_status in ('PENDING', 'ACTIVE', 'REJECTED', 'RESERVED', 'SOLD'):
            with self.subTest(status=unsafe_status):
                serializer = SaleListingInputSerializer(data={
                    'book_id': 1,
                    'price': '10.0000',
                    'status': unsafe_status,
                })
                self.assertFalse(serializer.is_valid())
                self.assertIn('status', serializer.errors)

    def test_checkout_does_not_accept_client_controlled_amount_or_status(self):
        serializer = CheckoutInputSerializer(data={
            'idempotency_key': 'checkout-1',
            'total_amount': '0.01',
            'payment_status': 'PAID',
            'order_status': 'COMPLETED',
            'seller_amount': '999999',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            set(serializer.validated_data),
            {
                'idempotency_key',
                'shipping_address_snapshot',
                'payment_outcome',
                'payment_method',
            },
        )
        self.assertEqual(serializer.validated_data['payment_outcome'], 'SUCCESS')

    def test_checkout_payment_outcomes_are_limited_to_fake_provider_results(self):
        for outcome in ('SUCCESS', 'FAILURE', 'CANCEL'):
            with self.subTest(outcome=outcome):
                serializer = CheckoutInputSerializer(data={
                    'idempotency_key': f'checkout-{outcome.lower()}',
                    'payment_outcome': outcome,
                })
                self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer = CheckoutInputSerializer(data={
            'idempotency_key': 'checkout-invalid',
            'payment_outcome': 'PAID',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('payment_outcome', serializer.errors)

    def test_checkout_requires_valid_recipient_and_address(self):
        for payload in (
            {},
            {
                'recipient_name': 'Buyer',
                'phone': '0900000000',
                'address_line': '1 Example Street',
            },
            {
                'recipient_name': ' ',
                'phone': '0900000000',
                'address_line': '1 Example Street',
                'city': 'Ho Chi Minh City',
            },
        ):
            with self.subTest(payload=payload):
                serializer = CheckoutAddressInputSerializer(data=payload)
                self.assertFalse(serializer.is_valid())

class ReservationAuthorizationTests(SimpleTestCase):
    def test_borrow_reservation_confirm_and_return_update_listing_without_order(self):
        now = timezone.now()
        book = SimpleNamespace(
            id=5,
            status='RESERVED',
            updated_at=None,
            sale_listings=Mock(),
            save=Mock(),
        )
        reservation = SimpleNamespace(
            id=14,
            book_id=book.id,
            book=book,
            status='PENDING',
            expires_at=now + timedelta(hours=1),
            owner_id=7,
            requester_id=8,
            updated_at=None,
            save=Mock(),
        )
        listing = SimpleNamespace(
            status='RESERVED',
            updated_at=None,
            save=Mock(),
        )
        reservation_query = Mock()
        reservation_query.get.return_value = reservation
        reservation_manager = Mock()
        reservation_manager.select_for_update.return_value = reservation_query
        book_manager = Mock()
        book_manager.select_for_update.return_value.get.return_value = book
        lend_manager = Mock()
        lend_manager.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = listing
        borrower = SimpleNamespace(id=8)

        with patch.object(BookReservation, 'objects', reservation_manager), patch(
            'books.services.Book.objects',
            book_manager,
        ), patch('books.services.LendListing.objects', lend_manager), patch(
            'books.services._notify',
        ), patch('books.services.BorrowOrder.objects.create') as create_borrow_order:
            confirmed = transition_reservation.__wrapped__(
                reservation.id,
                SimpleNamespace(id=7),
                'confirm',
            )
            self.assertEqual(confirmed.status, 'CONFIRMED')
            self.assertEqual(listing.status, 'ON_LOAN')
            self.assertEqual(book.status, 'ON_LOAN')

            returned = transition_reservation.__wrapped__(
                reservation.id,
                borrower,
                'complete',
            )

        self.assertEqual(returned.status, 'COMPLETED')
        self.assertEqual(listing.status, 'ACTIVE')
        self.assertEqual(book.status, 'AVAILABLE')
        create_borrow_order.assert_not_called()

    def test_outsider_cannot_trigger_expiration_side_effects(self):
        now = timezone.now()
        reservation = SimpleNamespace(
            id=14,
            book_id=5,
            status='PENDING',
            expires_at=now - timedelta(seconds=1),
            owner_id=7,
            requester_id=8,
            updated_at=None,
            save=Mock(),
        )
        reservation.book = SimpleNamespace(
            id=5,
            status='RESERVED',
            sale_listings=Mock(),
            save=Mock(),
        )
        query = Mock()
        query.get.return_value = reservation
        manager = Mock()
        manager.select_for_update.return_value = query
        book_manager = Mock()
        book_manager.select_for_update.return_value.get.return_value = reservation.book
        outsider = SimpleNamespace(id=99)

        with patch.object(BookReservation, 'objects', manager), patch(
            'books.services.Book.objects',
            book_manager,
        ):
            with self.assertRaises(PermissionDenied):
                transition_reservation.__wrapped__(14, outsider, 'confirm')

        self.assertEqual(reservation.status, 'PENDING')
        self.assertEqual(reservation.book.status, 'RESERVED')
        reservation.save.assert_not_called()
        reservation.book.save.assert_not_called()
        reservation.book.sale_listings.select_for_update.assert_not_called()
        manager.select_for_update.assert_called_once_with()

    def test_outsider_cannot_complete_another_users_reservation(self):
        reservation = SimpleNamespace(
            book_id=5,
            status='CONFIRMED',
            expires_at=timezone.now() + timedelta(minutes=5),
            owner_id=7,
            requester_id=8,
            save=Mock(),
            book=SimpleNamespace(
                status='RESERVED',
                sale_listings=Mock(),
                save=Mock(),
            ),
        )
        query = Mock()
        query.get.return_value = reservation
        manager = Mock()
        manager.select_for_update.return_value = query
        book_manager = Mock()
        book_manager.select_for_update.return_value.get.return_value = reservation.book

        with patch.object(BookReservation, 'objects', manager), patch(
            'books.services.Book.objects',
            book_manager,
        ):
            with self.assertRaises(PermissionDenied):
                transition_reservation.__wrapped__(
                    14,
                    SimpleNamespace(id=99),
                    'complete',
                )

        self.assertEqual(reservation.status, 'CONFIRMED')
        reservation.save.assert_not_called()
        reservation.book.save.assert_not_called()


class BookRequestOwnershipTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(id=10, is_authenticated=True)

    def test_user_cannot_edit_or_cancel_another_users_request(self):
        item = SimpleNamespace(
            id=21,
            user_id=20,
            status='OPEN',
            save=Mock(),
        )
        for method in ('patch', 'delete'):
            with self.subTest(method=method):
                request = (
                    self.factory.patch('/api/book-requests/21/', {'title_keyword': 'x'})
                    if method == 'patch'
                    else self.factory.delete('/api/book-requests/21/')
                )
                force_authenticate(request, user=self.user)
                with patch(
                    'books.request_api_views.get_object_or_404',
                    return_value=item,
                ):
                    response = BookRequestDetailView.as_view()(
                        request,
                        request_id=21,
                    )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(item.status, 'OPEN')
                item.save.assert_not_called()

    def test_client_cannot_set_request_status(self):
        from .request_api_views import BookRequestInputSerializer

        serializer = BookRequestInputSerializer(data={
            'request_type': 'BUY',
            'title_keyword': 'Biology',
            'status': 'CANCELLED',
            'user_id': 99,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('status', serializer.validated_data)
        self.assertNotIn('user', serializer.validated_data)


class PaymentInputSecurityTests(SimpleTestCase):
    def test_client_cannot_choose_amount_status_or_seller_amount(self):
        serializer = PaymentInputSerializer(data={
            'provider': 'unconfigured-provider',
            'payment_method': 'CARD',
            'idempotency_key': 'checkout-1',
            'amount': '0.01',
            'status': 'PAID',
            'seller_amount': '999999',
            'platform_fee': '0',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            set(serializer.validated_data),
            {'provider', 'payment_method', 'idempotency_key'},
        )

    def test_payment_creation_uses_order_total_and_pending_status(self):
        from decimal import Decimal

        factory = APIRequestFactory()
        buyer = SimpleNamespace(id=10, is_authenticated=True)
        order = SimpleNamespace(
            id=31,
            buyer_id=buyer.id,
            seller_id=20,
            total_amount=Decimal('125.5000'),
            currency='VND',
            checkout_group=SimpleNamespace(id=4),
        )
        payment = SimpleNamespace(
            id=71,
            order_id=order.id,
            amount=Decimal('125.5000'),
            platform_fee_rate=Decimal('0'),
            platform_fee=Decimal('0'),
            seller_amount=Decimal('125.5000'),
            status='PENDING',
            paid_at=None,
        )
        payment_manager = Mock()
        payment_manager.get_or_create.return_value = (payment, True)
        request = factory.post('/api/orders/31/payments/', {
            'provider': 'not-integrated',
            'payment_method': 'CARD',
            'idempotency_key': 'order-31',
            'amount': '0.01',
            'platform_fee': '0',
            'seller_amount': '999999',
            'status': 'PAID',
        }, format='json')
        request.user = buyer
        request.data = {
            'provider': 'fake',
            'payment_method': 'CARD',
            'idempotency_key': 'order-31',
            'amount': '0.01',
            'platform_fee': '0',
            'seller_amount': '999999',
            'status': 'PAID',
        }

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ), patch.object(Payment, 'objects', payment_manager), patch(
            'books.commerce_api_views.timezone.now',
        ), patch(
            'books.commerce_api_views.get_payment_provider',
            return_value=FakePaymentProvider(),
        ):
            response = PaymentListCreateView.post.__wrapped__(
                PaymentListCreateView(),
                request,
                order_id=order.id,
            )

        self.assertEqual(response.status_code, 201)
        values = payment_manager.get_or_create.call_args.kwargs['defaults']
        self.assertEqual(values['amount'], order.total_amount)
        self.assertEqual(values['status'], 'PENDING')
        self.assertEqual(values['seller_amount'], order.total_amount)
        self.assertTrue(values['provider_transaction_code'].startswith('fake_'))

    def test_fake_payment_intent_is_idempotent_and_transitions_use_project_statuses(self):
        provider = FakePaymentProvider()
        first_reference = provider.create_payment_intent('retry-1', '10.0000', 'VND')
        second_reference = provider.create_payment_intent('retry-1', '10.0000', 'VND')
        self.assertEqual(first_reference, second_reference)
        self.assertEqual(provider.transition('PENDING', 'PAID'), 'PAID')
        self.assertEqual(provider.transition('PENDING', 'FAILED'), 'FAILED')
        self.assertEqual(provider.transition('PENDING', 'CANCELLED'), 'CANCELLED')
        self.assertEqual(provider.transition('FAILED', 'PENDING'), 'PENDING')
        self.assertTrue(
            provider.create_refund_intent('refund-1', first_reference, '10.0000', 'VND')
            .startswith('fake_refund_'),
        )
        with self.assertRaises(ValidationError):
            provider.transition('PAID', 'FAILED')

    def test_fake_payment_provider_cannot_be_enabled_in_production(self):
        with patch('books.services.settings.PASSBOOK_ENVIRONMENT', 'production'), patch(
            'books.services.settings.PASSBOOK_FAKE_PAYMENTS_ENABLED',
            True,
        ):
            with self.assertRaises(PaymentProviderUnavailable):
                get_payment_provider('fake')

    def test_fake_payment_transition_requires_local_admin(self):
        factory = APIRequestFactory()
        request = factory.post('/api/admin/fake-payments/71/transition/', {
            'status': 'PAID',
        }, format='json')
        request.user = SimpleNamespace(role='STUDENT')
        with patch(
            'books.commerce_api_views.fake_payments_enabled',
            return_value=True,
        ), patch('books.commerce_api_views.transition_fake_payment') as transition:
            with self.assertRaises(PermissionDenied):
                FakePaymentTransitionView.post.__wrapped__(
                    FakePaymentTransitionView(),
                    request,
                    payment_id=71,
                )
        transition.assert_not_called()

    def test_fake_payment_success_confirms_order_without_double_capture(self):
        order = SimpleNamespace(id=31, status='PENDING_PAYMENT', save=Mock())
        payment = SimpleNamespace(
            provider='fake',
            status='PENDING',
            order=order,
            order_id=order.id,
            paid_at=None,
            updated_at=None,
            save=Mock(),
        )
        manager = Mock()
        manager.only.return_value.get.return_value = payment
        manager.select_for_update.return_value.get.return_value = payment
        manager.select_for_update.return_value.filter.return_value.exists.return_value = False
        order_manager = Mock()
        order_manager.select_for_update.return_value.get.return_value = order
        with patch('books.services.settings.PASSBOOK_ENVIRONMENT', 'test'), patch(
            'books.services.settings.PASSBOOK_FAKE_PAYMENTS_ENABLED',
            True,
        ), patch('books.services.Payment.objects', manager), patch(
            'books.services.Order.objects',
            order_manager,
        ), patch(
            'books.services.get_object_or_404',
            return_value=payment,
        ):
            result = transition_fake_payment.__wrapped__(71, 'PAID')

        self.assertIs(result, payment)
        self.assertEqual(payment.status, 'PAID')
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(order.status, 'CONFIRMED')
        payment.save.assert_called_once()
        order.save.assert_called_once_with(update_fields=['status', 'updated_at'])

    def test_fake_refund_completion_updates_payment_to_refunded(self):
        payment = SimpleNamespace(
            id=71,
            status='PAID',
            amount=Decimal('20.0000'),
            provider_transaction_code='fake_abc',
            updated_at=None,
            save=Mock(),
        )
        refund = SimpleNamespace(
            id=81,
            pk=81,
            provider='fake',
            status='REQUESTED',
            payment=payment,
            payment_id=payment.id,
            idempotency_key='refund-81',
            amount=Decimal('20.0000'),
            currency='VND',
            completed_at=None,
            updated_at=None,
            provider_refund_reference=None,
            save=Mock(),
        )
        refund_manager = Mock()
        refund_manager.select_for_update.return_value.filter.return_value.exclude.return_value.aggregate.return_value = {
            'total': Decimal('0'),
        }
        payment_manager = Mock()
        payment_manager.select_for_update.return_value.get.return_value = payment
        with patch('books.services.settings.PASSBOOK_ENVIRONMENT', 'test'), patch(
            'books.services.settings.PASSBOOK_FAKE_PAYMENTS_ENABLED',
            True,
        ), patch('books.services.Refund.objects', refund_manager), patch(
            'books.services.Payment.objects',
            payment_manager,
        ), patch(
            'books.services.get_object_or_404',
            return_value=refund,
        ):
            result = transition_fake_refund.__wrapped__(81, 'COMPLETED')

        self.assertIs(result, refund)
        self.assertEqual(refund.status, 'COMPLETED')
        self.assertTrue(refund.provider_refund_reference.startswith('fake_refund_'))
        self.assertEqual(payment.status, 'REFUNDED')
        refund.save.assert_called_once()
        payment.save.assert_called_once_with(update_fields=['status', 'updated_at'])

    def test_nonbuyer_cannot_create_payment_or_refund(self):
        factory = APIRequestFactory()
        order = SimpleNamespace(buyer_id=10)
        outsider = SimpleNamespace(id=99, is_authenticated=True)

        payment_request = factory.post('/api/orders/31/payments/', {}, format='json')
        payment_request.user = outsider
        payment_manager = Mock()
        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ), patch.object(Payment, 'objects', payment_manager):
            with self.assertRaises(PermissionDenied):
                PaymentListCreateView.post.__wrapped__(
                    PaymentListCreateView(),
                    payment_request,
                    order_id=31,
                )
        payment_manager.create.assert_not_called()

        refund_request = factory.post('/api/orders/31/refunds/', {}, format='json')
        refund_request.user = outsider
        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ), patch('books.commerce_api_views.Refund.objects.create') as create_refund:
            with self.assertRaises(PermissionDenied):
                RefundCreateView.post.__wrapped__(
                    RefundCreateView(),
                    refund_request,
                    order_id=31,
                )
        create_refund.assert_not_called()

    def test_refund_retry_returns_existing_refund_after_payment_is_refunded(self):
        from decimal import Decimal

        order = SimpleNamespace(id=31, buyer_id=10)
        payment = SimpleNamespace(id=80, provider='fake', status='REFUNDED')
        refund = SimpleNamespace(
            id=22,
            order_id=31,
            payment_id=80,
            amount=Decimal('170000.0000'),
            reason='Acceptance workflow test',
            sale_order_item_id=91,
            borrow_order_id=None,
            return_record_id=22,
            status='COMPLETED',
        )
        return_record = SimpleNamespace(
            id=22,
            sale_order_item_id=91,
            status='COMPLETED',
            sale_order_item=SimpleNamespace(id=91),
        )
        request = SimpleNamespace(
            user=SimpleNamespace(id=10, is_authenticated=True),
            data={
                'payment_id': 80,
                'return_id': 22,
                'idempotency_key': 'acceptance-refund-order-113-v1',
                'reason': 'Acceptance workflow test',
                'amount': '170000.0000',
            },
        )
        refund_query = Mock()
        refund_query.filter.return_value.first.return_value = refund

        with patch(
            'books.commerce_api_views.get_object_or_404',
            side_effect=(order, payment, return_record),
        ), patch(
            'books.commerce_api_views.Refund.objects.select_for_update',
            return_value=refund_query,
        ), patch(
            'books.commerce_api_views.Refund.objects.filter',
        ) as create_path_query, patch(
            'books.commerce_api_views.Refund.objects.create',
        ) as create_refund:
            response = RefundCreateView.post.__wrapped__(
                RefundCreateView(),
                request,
                order_id=31,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], 22)
        self.assertEqual(response.data['status'], 'COMPLETED')
        create_path_query.assert_not_called()
        create_refund.assert_not_called()

    def test_nonparticipant_cannot_read_order_details(self):
        from rest_framework.test import force_authenticate

        factory = APIRequestFactory()
        outsider = SimpleNamespace(id=99, is_authenticated=True)
        order = SimpleNamespace(buyer_id=10, seller_id=20)
        request = factory.get('/api/orders/31/')
        force_authenticate(request, user=outsider)

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ):
            response = OrderDetailView.as_view()(request, order_id=31)

        self.assertEqual(response.status_code, 403)


class BorrowOrderAuthorizationTests(SimpleTestCase):
    def test_outsider_cannot_reject_borrow_order(self):
        borrow_order = SimpleNamespace(
            id=18,
            status='PENDING',
            lender_id=10,
            borrower_id=11,
            order=SimpleNamespace(status='PENDING_PAYMENT', save=Mock()),
            lend_listing=SimpleNamespace(
                status='RESERVED',
                save=Mock(),
                book=SimpleNamespace(status='RESERVED', save=Mock()),
            ),
            save=Mock(),
        )
        query = Mock()
        query.select_related.return_value = query
        query.get.return_value = borrow_order
        manager = Mock()
        manager.select_for_update.return_value = query

        with patch('books.services.BorrowOrder.objects', manager):
            with self.assertRaises(PermissionDenied):
                transition_borrow_order.__wrapped__(
                    18,
                    SimpleNamespace(id=99),
                    'reject',
                )

        self.assertEqual(borrow_order.status, 'PENDING')
        self.assertEqual(borrow_order.order.status, 'PENDING_PAYMENT')
        self.assertEqual(borrow_order.lend_listing.status, 'RESERVED')
        borrow_order.save.assert_not_called()
        borrow_order.order.save.assert_not_called()
        borrow_order.lend_listing.save.assert_not_called()
        borrow_order.lend_listing.book.save.assert_not_called()

    def test_nonowner_cannot_process_return(self):
        factory = APIRequestFactory()
        outsider = SimpleNamespace(id=99, is_authenticated=True)
        return_record = SimpleNamespace(
            id=7,
            status='REQUESTED',
            order=SimpleNamespace(seller_id=20),
            save=Mock(),
        )
        request = factory.post('/api/returns/7/approve/', {}, format='json')
        request.user = outsider

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=return_record,
        ):
            with self.assertRaises(PermissionDenied):
                ReturnActionView.post.__wrapped__(
                    ReturnActionView(),
                    request,
                    return_id=7,
                    action='approve',
                )

        self.assertEqual(return_record.status, 'REQUESTED')
        return_record.save.assert_not_called()
