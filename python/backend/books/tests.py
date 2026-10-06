import json
import re
from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.contrib import admin
from django.apps import apps
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from config.cloudinary import verify_cloudinary_image
from config.composite_admin import CompositeKeyAdmin
from .category_taxonomy import BOOK_CATEGORIES, is_supported_book_category
from .models import (
    Book,
    BookReservation,
    BorrowTerms,
    BorrowOrder,
    CheckoutGroup,
    LendListing,
    Order,
    Payment,
    SaleListing,
    Shipment,
    ShipmentTracking,
)
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
from .shipment_services import update_shipment_status
from .sale_api_views import SaleListingDetailView, SaleListingInputSerializer
from .commerce_api_views import (
    BookReservationListCreateView,
    BorrowOrderActionView,
    BorrowOrderReturnRequestView,
    BorrowReturnInputSerializer,
    CartItemInputSerializer,
    CheckoutView,
    FakePaymentTransitionView,
    OrderDetailView,
    PaymentInputSerializer,
    PaymentListCreateView,
    RefundCreateView,
    ReviewCreateView,
    ReviewInputSerializer,
    ReturnActionView,
    ShipmentTrackingCreateView,
    CheckoutAddressInputSerializer,
    CheckoutInputSerializer,
    LendListingInputSerializer,
    LendListingListCreateView,
    checkout_payment_method,
    lend_listing_payload,
)
from .admin import LendListingAdmin
from .public_profile_api_views import PublicUserListingsView
from .api_views import (
    BookDetailView,
    BookImageListView,
    _attach_listing_response_data,
    prefetch_book_reviews,
    prefetch_book_rating_summaries,
)
from .request_api_views import (
    BookIntentSummaryView,
    BookRequestDetailView,
    BookRequestInterestView,
    BookRequestInputSerializer,
    request_payload,
)
from users.models import OtpVerification


class BookCategoryTaxonomyTests(SimpleTestCase):
    def test_taxonomy_contains_exactly_the_supported_ordered_categories(self):
        self.assertEqual(
            [name for _slug, name, _description in BOOK_CATEGORIES],
            [
                'Tiểu thuyết',
                'Thơ',
                'Kịch',
                'Sách giáo khoa',
                'Giáo trình',
                'Tài liệu',
                'Truyện tranh',
            ],
        )
        self.assertEqual(
            [slug for slug, _name, _description in BOOK_CATEGORIES],
            [
                'tieu-thuyet',
                'tho',
                'kich',
                'sach-giao-khoa',
                'giao-trinh',
                'tai-lieu',
                'truyen-tranh',
            ],
        )
        self.assertTrue(is_supported_book_category(None))
        self.assertTrue(is_supported_book_category(SimpleNamespace(
            slug='tieu-thuyet',
            status='ACTIVE',
        )))
        self.assertFalse(is_supported_book_category(SimpleNamespace(
            slug='legacy-category',
            status='ACTIVE',
        )))


class BookReviewPrefetchTests(SimpleTestCase):
    def test_reviews_are_batched_for_books_and_read_from_prefetch(self):
        reviewer = SimpleNamespace(id=8, full_name='Reviewer')
        review = SimpleNamespace(
            id=12,
            rating=5,
            comment='Good book',
            created_at=timezone.now(),
            reviewer_id=8,
            reviewer=reviewer,
            sale_listing=SimpleNamespace(book_id=1),
            lend_listing=None,
        )
        query = Mock()
        filtered_query = Mock()
        query.filter.return_value = filtered_query
        filtered_query.select_related.return_value.only.return_value.order_by.return_value = [
            review,
        ]
        books = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        with patch('books.api_views.Review.objects.filter', return_value=query) as filter_reviews:
            prefetch_book_reviews(books)

        filter_reviews.assert_called_once()
        query.filter.assert_called_once_with(
            reviewer_id=F('order__buyer_id'),
            order__status='COMPLETED',
        )
        self.assertEqual(
            BookSerializer.get_reviews(books[0])[0]['reviewer'],
            {'id': 8, 'name': 'Reviewer'},
        )
        self.assertEqual(BookSerializer.get_average_rating(books[0]), 5)
        self.assertEqual(BookSerializer.get_review_count(books[0]), 1)
        self.assertEqual(books[0]._book_average_rating, 5)
        self.assertEqual(books[0]._book_review_count, 1)
        self.assertEqual(BookSerializer.get_reviews(books[1]), [])
        self.assertIsNone(books[1]._book_average_rating)

    def test_rating_summaries_are_batched_and_default_for_unrated_books(self):
        query = Mock()
        filtered_query = Mock()
        query.filter.return_value = filtered_query
        filtered_query.annotate.return_value.values.return_value.annotate.return_value = [
            {'_book_id': 1, 'average_rating': 4.25, 'review_count': 4},
        ]
        books = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        with patch(
            'books.api_views.Review.objects.filter',
            return_value=query,
        ) as filter_reviews:
            prefetch_book_rating_summaries(books)

        filter_reviews.assert_called_once()
        query.filter.assert_called_once_with(
            reviewer_id=F('order__buyer_id'),
            order__status='COMPLETED',
        )
        self.assertEqual(books[0]._book_average_rating, 4.2)
        self.assertEqual(books[0]._book_review_count, 4)
        self.assertIsNone(books[1]._book_average_rating)
        self.assertEqual(books[1]._book_review_count, 0)


class ReviewCreateAuthorizationTests(SimpleTestCase):
    def test_review_input_enforces_rating_bounds_and_comment_limit(self):
        invalid_rating = ReviewInputSerializer(data={'rating': 0})
        oversized_comment = ReviewInputSerializer(data={
            'rating': 5,
            'comment': 'a' * 5001,
        })

        self.assertFalse(invalid_rating.is_valid())
        self.assertFalse(oversized_comment.is_valid())

    def test_only_completed_order_buyer_can_rate_the_book(self):
        order = SimpleNamespace(
            id=31,
            status='COMPLETED',
            buyer_id=10,
            seller_id=20,
        )
        request = APIRequestFactory().post(
            '/api/orders/31/reviews/',
            {'rating': 5, 'comment': 'Rất tốt'},
            format='json',
        )
        force_authenticate(
            request,
            user=SimpleNamespace(id=20, is_authenticated=True),
        )

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ), patch('books.commerce_api_views.Review.objects.get_or_create') as create_review:
            response = ReviewCreateView.as_view()(request, order_id=31)

        self.assertEqual(response.status_code, 403)
        create_review.assert_not_called()

    def test_buyer_rating_is_saved_for_the_order_listing(self):
        listing = SimpleNamespace(id=12)
        order = SimpleNamespace(
            id=31,
            status='COMPLETED',
            buyer_id=10,
            seller_id=20,
            order_type='SALE',
            sale_items=Mock(),
        )
        order.sale_items.select_related.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            sale_listing=listing,
        )
        review = SimpleNamespace(
            id=44,
            order_id=31,
            rating=5,
            comment='Rất tốt',
            created_at=timezone.now(),
            reviewer_id=10,
            reviewer=SimpleNamespace(full_name='Buyer'),
        )
        request = APIRequestFactory().post(
            '/api/orders/31/reviews/',
            {'rating': 5, 'comment': 'Rất tốt'},
            format='json',
        )
        force_authenticate(
            request,
            user=SimpleNamespace(id=10, is_authenticated=True),
        )

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=order,
        ), patch(
            'books.commerce_api_views.Review.objects.get_or_create',
            return_value=(review, True),
        ) as create_review:
            response = ReviewCreateView.as_view()(request, order_id=31)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['reviewer']['name'], 'Buyer')
        self.assertEqual(
            create_review.call_args.kwargs['defaults']['sale_listing'],
            listing,
        )


class PublicUserListingsApiTests(SimpleTestCase):
    class ListingRows:
        def __init__(self, rows):
            self.rows = rows

        def count(self):
            return len(self.rows)

        def __getitem__(self, key):
            return self.rows[key]

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user_id = 72
        self.sale = self._listing('SALE', listing_id=101, book_id=501, created=3)
        self.borrow = self._listing('BORROW', listing_id=102, book_id=502, created=2)
        self.other_sale = self._listing('SALE', listing_id=103, book_id=503, created=1)

    @staticmethod
    def _listing(listing_type, *, listing_id, book_id, created):
        university = SimpleNamespace(id=7, name='Local University')
        seller = SimpleNamespace(
            id=72,
            full_name='Public Seller',
            university_id=university.id,
            university=university,
        )
        category = SimpleNamespace(id=3, name='Giáo trình')
        subject = SimpleNamespace(id=9, name='Vật lý', code='PHY101')
        work = SimpleNamespace(
            category_id=category.id,
            category=category,
            primary_subject_links=[SimpleNamespace(subject=subject)],
        )
        edition = SimpleNamespace(
            book_work=work,
            edition_name='Local edition',
            publication_year=2025,
        )
        book = SimpleNamespace(
            id=book_id,
            condition_status='like_new',
            condition_label='LIKE_NEW',
            book_edition=edition,
            public_primary_images=[
                SimpleNamespace(
                    id=listing_id,
                    image_url=f'https://example.invalid/{book_id}.jpg',
                    is_primary=True,
                ),
            ],
        )
        return SimpleNamespace(
            id=listing_id,
            book=book,
            seller=seller,
            lender=seller,
            title=f'Public book {book_id}',
            price=Decimal('120000'),
            rental_fee=Decimal('10000'),
            deposit_amount=Decimal('50000'),
            created_at=timezone.now() + timedelta(seconds=created),
            public_listing_terms=SimpleNamespace(
                max_days=14,
                deposit_required=True,
            ),
            listing_type=listing_type,
        )

    def _request(self, params=None):
        request = self.factory.get(
            f'/api/users/{self.user_id}/listings/',
            params or {},
            HTTP_HOST='localhost',
        )
        with patch(
            'books.public_profile_api_views.get_object_or_404',
        ) as get_user, patch(
            'books.public_profile_api_views._listing_queryset',
            side_effect=lambda kind, _user_id, _now: self.ListingRows(
                [self.sale, self.other_sale] if kind == 'SALE' else [self.borrow],
            ),
        ):
            get_user.return_value = SimpleNamespace(id=self.user_id)
            response = PublicUserListingsView.as_view()(request, user_id=self.user_id)
        return response

    def test_public_all_filter_merges_sale_and_borrow_with_pagination(self):
        response = self._request({'type': 'ALL', 'page_size': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['sale_count'], 2)
        self.assertEqual(response.data['borrow_count'], 1)
        self.assertEqual(
            [item['listing_type'] for item in response.data['results']],
            ['SALE', 'BORROW'],
        )
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        self.assertEqual(response.data['results'][0]['id'], self.sale.book.id)
        self.assertEqual(response.data['results'][1]['listing_id'], self.borrow.id)
        self.assertEqual(response.data['results'][1]['borrow_terms']['max_days'], 14)
        for item in response.data['results']:
            self.assertNotIn('phone', item['seller'])
            self.assertNotIn('email', item['seller'])
            self.assertNotIn('password_hash', item['seller'])

        second_page = self._request({'type': 'ALL', 'page': '2', 'page_size': '2'})
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(
            [item['listing_id'] for item in second_page.data['results']],
            [self.other_sale.id],
        )
        self.assertIsNotNone(second_page.data['previous'])
        self.assertIsNone(second_page.data['next'])

    def test_public_type_filters_return_only_the_requested_listing_kind(self):
        for kind, expected_id in (('SALE', 101), ('BORROW', 102)):
            with self.subTest(kind=kind):
                response = self._request({'type': kind})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 2 if kind == 'SALE' else 1)
                self.assertTrue(all(
                    item['listing_type'] == kind
                    for item in response.data['results']
                ))
                self.assertEqual(response.data['results'][0]['listing_id'], expected_id)

    def test_invalid_public_listing_filter_is_rejected(self):
        response = self._request({'type': 'DRAFT'})
        self.assertEqual(response.status_code, 400)


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
        result = calculate_payment_split('100000', '0.10')
        self.assertEqual(result['subtotal'], 100000)
        self.assertEqual(result['amount'], 100000)
        self.assertEqual(result['platform_fee'], 10000)
        self.assertEqual(result['seller_amount'], 90000)
        self.assertEqual(
            calculate_payment_split('100000', '0.10'),
            result,
        )

    def test_fee_rate_must_be_between_zero_and_one(self):
        for rate in ('-0.01', '1.01'):
            with self.subTest(rate=rate):
                with self.assertRaises(ValidationError):
                    calculate_payment_split('100000', rate)


    def test_online_checkout_method_is_accepted(self):
        serializer = CheckoutInputSerializer(data={
            'idempotency_key': 'checkout-online-1',
            'cart_item_id': 1,
            'payment_method': 'ONLINE',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)


class FavoritePayloadTests(SimpleTestCase):
    def test_favorite_book_uses_the_compact_card_payload(self):
        self.assertEqual(
            set(FavoriteBookSerializer().fields),
            set(BookListSerializer().fields),
        )
        self.assertNotIn('description', FavoriteBookSerializer().fields)
        self.assertNotIn('images', FavoriteBookSerializer().fields)


class LegacyBookInputCompatibilityTests(SimpleTestCase):
    def test_book_input_accepts_a_custom_subject_name(self):
        serializer = BookWriteSerializer(data={
            'title': 'Custom subject book',
            'price': '100000',
            'condition_status': 'good',
            'subject_name': '  Biochemistry  ',
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['subject_name'], 'Biochemistry')

    @patch('books.serializers.transaction.atomic', return_value=nullcontext())
    @patch('books.serializers.Subject.objects.create')
    @patch('books.serializers.Subject.objects.filter')
    def test_custom_subject_name_creates_active_catalog_subject(
        self,
        filter_subjects,
        create_subject,
        atomic,
    ):
        filter_subjects.return_value.order_by.return_value.first.return_value = None
        subject = Mock(status='ACTIVE')
        create_subject.return_value = subject
        now = timezone.now()

        result = BookWriteSerializer._subject_from_name('Biochemistry', now)

        self.assertIs(result, subject)
        create_subject.assert_called_once()
        created = create_subject.call_args.kwargs
        self.assertEqual(created['name'], 'Biochemistry')
        self.assertEqual(created['status'], 'ACTIVE')
        self.assertEqual(created['created_at'], now)
        self.assertEqual(created['updated_at'], now)
        self.assertTrue(created['code'].startswith('USR_BIOCHEMISTRY_'))

    @patch('books.serializers.transaction.atomic', return_value=nullcontext())
    @patch('books.serializers.Subject.objects.create')
    @patch('books.serializers.Subject.objects.filter')
    def test_existing_subject_name_reuses_active_catalog_subject(
        self,
        filter_subjects,
        create_subject,
        atomic,
    ):
        subject = Mock(status='ACTIVE')
        filter_subjects.return_value.order_by.return_value.first.return_value = subject

        result = BookWriteSerializer._subject_from_name('Biochemistry', timezone.now())

        self.assertIs(result, subject)
        create_subject.assert_not_called()

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

    def test_borrow_listing_choices_are_validated(self):
        base = {
            'listing_type': 'BORROW',
            'title': 'Borrow listing',
            'rental_fee': '0',
            'condition_status': 'good',
            'max_days': 14,
            'shipping_paid_by': 'BORROWER',
            'return_method': 'IN_PERSON',
        }
        self.assertTrue(BookWriteSerializer(data=base).is_valid())
        for field, invalid_value in (
            ('shipping_paid_by', 'SOMEONE_ELSE'),
            ('return_method', 'UNSUPPORTED'),
        ):
            with self.subTest(field=field):
                payload = {**base, field: invalid_value}
                serializer = BookWriteSerializer(data=payload)
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_lend_listing_endpoint_validates_borrow_term_choices(self):
        base = {
            'book_id': 1,
            'rental_fee': '0',
            'max_days': 14,
            'shipping_paid_by': 'BORROWER',
            'return_method': 'IN_PERSON',
        }
        self.assertTrue(LendListingInputSerializer(data=base).is_valid())
        for field, invalid_value in (
            ('shipping_paid_by', 'SOMEONE_ELSE'),
            ('return_method', 'UNSUPPORTED'),
        ):
            with self.subTest(field=field):
                serializer = LendListingInputSerializer(data={
                    **base,
                    field: invalid_value,
                })
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_deposit_is_never_mandatory_for_new_borrow_listings(self):
        serializer = BookWriteSerializer(data={
            'listing_type': 'BORROW',
            'title': 'Borrow listing',
            'rental_fee': '0',
            'condition_status': 'good',
            'max_days': 14,
            'shipping_paid_by': 'BORROWER',
            'return_method': 'IN_PERSON',
            'deposit_amount': '250000',
            'deposit_required': True,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('deposit_required', serializer.validated_data)

    def test_active_listing_edit_is_queued_for_review_again(self):
        listing = SimpleNamespace(
            status='ACTIVE',
            title='Old title',
            description=None,
            published_at=timezone.now(),
            updated_at=None,
            save=Mock(),
        )
        work = SimpleNamespace(
            title='Old title',
            description=None,
            author_name=None,
            category=None,
            updated_at=None,
            save=Mock(),
        )
        edition = SimpleNamespace(
            book_work=work,
            edition_name=None,
            publication_year=None,
            publisher_name=None,
            updated_at=None,
            save=Mock(),
        )
        book = SimpleNamespace(
            pk=10,
            book_edition=edition,
            condition_label='GOOD',
            condition_description=None,
            updated_at=None,
            save=Mock(),
            sale_listings=Mock(),
            lend_listings=Mock(),
        )
        book.sale_listings.filter.return_value.first.return_value = listing
        book.lend_listings.filter.return_value.first.return_value = None

        with patch('books.serializers.transaction.atomic', return_value=nullcontext()):
            BookWriteSerializer().update(book, {'title': 'Updated title'})

        self.assertEqual(listing.status, 'PENDING')
        self.assertIsNone(listing.published_at)
        self.assertEqual(listing.title, 'Updated title')
        listing.save.assert_called_once()

    def test_editing_active_borrow_listing_removes_required_deposit(self):
        listing = SimpleNamespace(
            status='ACTIVE',
            title='Old title',
            description=None,
            published_at=timezone.now(),
            updated_at=None,
            save=Mock(),
        )
        terms = SimpleNamespace(
            max_days=14,
            late_fee_per_day=None,
            deposit_required=True,
            shipping_paid_by='BORROWER',
            return_method='IN_PERSON',
            notes='',
            updated_at=None,
            save=Mock(),
        )
        listing.listing_terms = terms
        work = SimpleNamespace(
            title='Old title',
            description=None,
            author_name=None,
            category=None,
            updated_at=None,
            save=Mock(),
        )
        edition = SimpleNamespace(
            book_work=work,
            edition_name=None,
            publication_year=None,
            publisher_name=None,
            updated_at=None,
            save=Mock(),
        )
        book = SimpleNamespace(
            pk=11,
            book_edition=edition,
            condition_label='GOOD',
            condition_description=None,
            updated_at=None,
            save=Mock(),
            sale_listings=Mock(),
            lend_listings=Mock(),
        )
        book.sale_listings.filter.return_value.first.return_value = None
        book.lend_listings.filter.return_value.first.return_value = listing

        with patch('books.serializers.transaction.atomic', return_value=nullcontext()):
            BookWriteSerializer().update(book, {'title': 'Updated title'})

        self.assertEqual(listing.status, 'PENDING')
        self.assertIsNone(listing.published_at)
        self.assertFalse(terms.deposit_required)
        terms.save.assert_called_once()

    @patch('books.api_views.LendListing.objects.filter')
    @patch('books.api_views.SaleListing.objects.filter')
    def test_new_pending_borrow_listing_is_returned_as_borrow(
        self,
        sale_filter,
        lend_filter,
    ):
        terms = SimpleNamespace(
            max_days=14,
            late_fee_per_day=Decimal('0'),
            deposit_required=False,
            shipping_paid_by='BORROWER',
            return_method='IN_PERSON',
            notes='',
        )
        listing = SimpleNamespace(
            id=43,
            status='PENDING',
            rental_fee=Decimal('0'),
            deposit_amount=None,
            listing_terms=terms,
        )
        sale_filter.return_value.order_by.return_value.first.return_value = None
        lend_filter.return_value.prefetch_related.return_value.order_by.return_value.first.return_value = listing
        book = SimpleNamespace(
            pk=21,
            _active_sale_listing=Mock(return_value=None),
            _active_lend_listing=Mock(return_value=listing),
        )

        _attach_listing_response_data(book)

        self.assertEqual(BookSerializer.get_listing_type(book), 'BORROW')
        self.assertEqual(BookSerializer.get_listing_id(book), 43)
        self.assertEqual(
            BookSerializer.get_borrow_terms(book)['shipping_paid_by'],
            'BORROWER',
        )

    def test_book_detail_metadata_can_be_entered_on_a_listing(self):
        serializer = BookWriteSerializer(data={
            'title': 'Complete detail metadata',
            'price': '100000',
            'condition_status': 'good',
            'author': 'A. Writer',
            'publisher': 'Campus Press',
            'isbn': '9781234567890',
            'condition_description': 'Notes and cover are in good condition.',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['author'], 'A. Writer')
        self.assertEqual(serializer.validated_data['publisher'], 'Campus Press')
        self.assertEqual(serializer.validated_data['isbn'], '9781234567890')
        self.assertEqual(
            serializer.validated_data['condition_description'],
            'Notes and cover are in good condition.',
        )


class BookImageManifestValidationTests(SimpleTestCase):
    @patch('books.serializers.verify_cloudinary_image')
    def test_single_image_becomes_primary_and_sort_order_starts_at_zero(self, verify):
        serializer = BookWriteSerializer(
            data={
                'title': 'Single image listing',
                'price': '100000',
                'condition_status': 'good',
                'images': [{
                    'image_url': 'https://res.cloudinary.com/demo/image/upload/book.jpg',
                    'cloudinary_public_id': f'user-8-{"a" * 32}',
                    'sort_order': 7,
                }],
            },
            context={'request': SimpleNamespace(user=SimpleNamespace(id=8))},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        image = serializer.validated_data['images'][0]
        self.assertTrue(image['is_primary'])
        self.assertEqual(image['sort_order'], 0)
        verify.assert_called_once()

    @patch('books.serializers.verify_cloudinary_image')
    def test_multi_image_manifest_uses_array_order_and_one_selected_primary(self, verify):
        serializer = BookWriteSerializer(
            data={
                'title': 'Multi image listing',
                'price': '100000',
                'condition_status': 'good',
                'images': [
                    {
                        'image_url': 'https://res.cloudinary.com/demo/image/upload/a.jpg',
                        'cloudinary_public_id': f'user-8-{"a" * 32}',
                        'sort_order': 9,
                    },
                    {
                        'image_url': 'https://res.cloudinary.com/demo/image/upload/b.jpg',
                        'cloudinary_public_id': f'user-8-{"b" * 32}',
                        'is_primary': True,
                        'sort_order': 9,
                    },
                    {
                        'image_url': 'https://res.cloudinary.com/demo/image/upload/c.jpg',
                        'cloudinary_public_id': f'user-8-{"c" * 32}',
                        'sort_order': 0,
                    },
                ],
            },
            context={'request': SimpleNamespace(user=SimpleNamespace(id=8))},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        images = serializer.validated_data['images']
        self.assertEqual([image['sort_order'] for image in images], [0, 1, 2])
        self.assertEqual(
            [image['is_primary'] for image in images],
            [False, True, False],
        )
        self.assertEqual(verify.call_count, 3)

    def test_manifest_allows_no_image_and_rejects_more_than_ten_images(self):
        no_image = BookWriteSerializer(data={
            'title': 'No image listing',
            'price': '100000',
            'condition_status': 'good',
        })
        self.assertTrue(no_image.is_valid(), no_image.errors)

        too_many = BookWriteSerializer(data={
            'title': 'Too many images',
            'price': '100000',
            'condition_status': 'good',
            'images': [
                {
                    'image_url': f'https://images.example.invalid/{index}.jpg',
                    'cloudinary_public_id': f'user-8-{index:032x}',
                }
                for index in range(11)
            ],
        })
        self.assertFalse(too_many.is_valid())
        self.assertIn('images', too_many.errors)

    def test_existing_image_ids_cannot_be_included_on_create(self):
        serializer = BookWriteSerializer(data={
            'title': 'Forged existing image',
            'price': '100000',
            'condition_status': 'good',
            'images': [{
                'id': 42,
                'image_url': 'https://images.example.invalid/book.jpg',
                'cloudinary_public_id': f'user-8-{"a" * 32}',
            }],
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('images', serializer.errors)


class CloudinaryImageValidationTests(SimpleTestCase):
    @override_settings(
        CLOUDINARY_CLOUD_NAME='test-cloud',
        CLOUDINARY_API_KEY='test-key',
        CLOUDINARY_API_SECRET='test-secret',
    )
    @patch('config.cloudinary.urllib.request.urlopen')
    def test_server_validates_cloudinary_format_size_and_url(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'public_id': f'user-8-{"a" * 32}',
            'secure_url': 'https://res.cloudinary.com/test-cloud/image/upload/book.jpg',
            'format': 'jpg',
            'bytes': 1024,
        }).encode()
        urlopen.return_value = response

        verify_cloudinary_image(
            user_id=8,
            image_url='https://res.cloudinary.com/test-cloud/image/upload/book.jpg',
            public_id=f'user-8-{"a" * 32}',
        )

        request = urlopen.call_args.args[0]
        self.assertIn('/resources/image/upload/', request.full_url)
        self.assertTrue(request.get_header('Authorization').startswith('Basic '))

    @override_settings(
        CLOUDINARY_CLOUD_NAME='test-cloud',
        CLOUDINARY_API_KEY='test-key',
        CLOUDINARY_API_SECRET='test-secret',
    )
    @patch('config.cloudinary.urllib.request.urlopen')
    def test_server_rejects_disallowed_format_and_oversized_image(self, urlopen):
        for image_format, byte_count in (('pdf', 1024), ('jpg', 10 * 1024 * 1024 + 1)):
            with self.subTest(image_format=image_format, byte_count=byte_count):
                response = MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps({
                    'public_id': f'user-8-{"a" * 32}',
                    'secure_url': 'https://res.cloudinary.com/test-cloud/image/upload/book.jpg',
                    'format': image_format,
                    'bytes': byte_count,
                }).encode()
                urlopen.return_value = response

                with self.assertRaises(ValidationError):
                    verify_cloudinary_image(
                        user_id=8,
                        image_url='https://res.cloudinary.com/test-cloud/image/upload/book.jpg',
                        public_id=f'user-8-{"a" * 32}',
                    )

    def test_upload_public_id_must_be_owned_by_the_authenticated_user(self):
        with self.assertRaises(ValidationError):
            verify_cloudinary_image(
                user_id=8,
                image_url='https://res.cloudinary.com/test-cloud/image/upload/book.jpg',
                public_id=f'user-9-{"a" * 32}',
            )


class BookImageOwnershipTests(SimpleTestCase):
    def test_user_cannot_upload_images_to_another_users_book(self):
        request = SimpleNamespace(
            user=SimpleNamespace(id=8, is_authenticated=True),
        )
        book = SimpleNamespace(id=32, owner_id=9, status='AVAILABLE')
        with patch('books.api_views.get_object_or_404', return_value=book):
            with self.assertRaises(PermissionDenied):
                BookImageListView._get_editable_book(request, 32)


class BorrowCheckoutTests(SimpleTestCase):
    def test_borrow_only_checkout_uses_cod_without_changing_sale_payment(self):
        borrow_lines = [(None, None, None)]
        sale_groups = {}
        self.assertEqual(
            checkout_payment_method('FAKE', sale_groups, borrow_lines),
            'COD',
        )
        self.assertEqual(
            checkout_payment_method('BANK_TRANSFER', {10: [None]}, borrow_lines),
            'BANK_TRANSFER',
        )
        self.assertEqual(
            checkout_payment_method('FAKE', sale_groups, []),
            'FAKE',
        )

    def test_cart_accepts_borrow_listing_type(self):
        serializer = CartItemInputSerializer(data={
            'listing_type': 'BORROW',
            'listing_id': 12,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_checkout_line_includes_lend_fee_and_deposit(self):
        listing = SimpleNamespace(
            id=12,
            lender_id=10,
            rental_fee=Decimal('25000.0000'),
            deposit_amount=Decimal('50000.0000'),
        )
        query = Mock()
        query.filter.return_value = query
        query.first.return_value = listing
        listing_manager = Mock()
        listing_manager.select_related.return_value = query
        terms = SimpleNamespace(max_days=14)
        item = SimpleNamespace(sale_listing_id=None, lend_listing_id=12)

        with patch(
            'books.commerce_api_views.LendListing.objects',
            listing_manager,
        ), patch(
            'books.commerce_api_views.BorrowTerms.objects.get',
            return_value=terms,
        ):
            line = CheckoutView._checkout_line(item, SimpleNamespace(id=8))

        self.assertEqual(line['listing_type'], 'BORROW')
        self.assertEqual(line['unit_price'], Decimal('75000.0000'))
        self.assertEqual(line['amount'], Decimal('75000.0000'))
        self.assertIs(line['terms'], terms)

    def test_checkout_requires_valid_future_dates_within_listing_limit(self):
        now = timezone.now()
        listing = SimpleNamespace(id=12, title='Test lend listing')
        terms = SimpleNamespace(max_days=2)
        dates = {
            '12': {
                'expected_start_at': now + timedelta(hours=1),
                'expected_return_at': now + timedelta(days=3),
            },
        }

        with self.assertRaisesMessage(ValidationError, 'tối đa 2 ngày'):
            CheckoutView._validate_borrow_dates(
                [(None, listing, terms)],
                dates,
                now,
            )

    def test_checkout_serializer_validates_borrow_date_fields(self):
        now = timezone.now()
        serializer = CheckoutInputSerializer(data={
            'idempotency_key': 'borrow-checkout-test',
            'borrow': {
                '12': {
                    'expected_start_at': (now + timedelta(hours=1)).isoformat(),
                    'expected_return_at': (now + timedelta(days=2)).isoformat(),
                },
            },
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_lend_listing_admin_can_approve_pending_listings(self):
        admin_instance = LendListingAdmin(LendListing, admin.site)
        request = SimpleNamespace()
        queryset = Mock()
        queryset.filter.return_value.update.return_value = 1
        with patch.object(admin_instance, '_report_moderation_result') as report:
            admin_instance.approve_pending(request, queryset)

        queryset.filter.assert_called_once_with(status='PENDING')
        report.assert_called_once_with(request, 1, 'approved')


class CheckoutQuoteTests(SimpleTestCase):
    def test_quote_returns_item_subtotal(self):
        item = SimpleNamespace(id=12)
        line = {
            'listing': SimpleNamespace(title='Acceptance book', currency='VND'),
            'unit_price': Decimal('100.0000'),
            'amount': Decimal('100.0000'),
        }
        request = SimpleNamespace(
            query_params={'cart_item_id': '12'},
            user=SimpleNamespace(id=8),
        )

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=item,
        ), patch.object(
            CheckoutView,
            '_checkout_line',
            return_value=line,
        ):
            response = CheckoutView().get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['items'][0]['subtotal'],
            response.data['subtotal'],
        )


class ReservationApiValidationTests(SimpleTestCase):
    def test_borrow_reservation_api_requires_cart_checkout(self):
        request = APIRequestFactory().post(
            '/api/books/6/reservations/',
            {},
            format='json',
        )
        request.user = SimpleNamespace(id=8, is_authenticated=True)
        with self.assertRaisesMessage(
            ValidationError,
            'Yêu cầu mượn phải được tạo và thanh toán qua giỏ hàng.',
        ):
            BookReservationListCreateView.post.__wrapped__(
                BookReservationListCreateView(),
                request,
                book_id=6,
            )


class CheckoutPhoneVerificationTests(SimpleTestCase):
    def test_checkout_does_not_require_phone_otp_or_trust_client_verification_flag(self):
        buyer = SimpleNamespace(id=42, is_authenticated=True, phone='+15550001111')
        serializer = Mock(validated_data={'idempotency_key': 'checkout-once'})
        serializer.is_valid.return_value = None
        request = SimpleNamespace(
            data={'phone_verified': False},
            user=buyer,
        )
        checkout_manager = Mock()
        checkout_manager.filter.return_value.first.return_value = None
        cart_manager = Mock()
        cart_manager.select_for_update.return_value.filter.return_value.first.return_value = None
        order_manager = Mock()
        payment_manager = Mock()

        with patch(
            'books.commerce_api_views.CheckoutInputSerializer',
            return_value=serializer,
        ), patch.object(
            CheckoutGroup,
            'objects',
            checkout_manager,
        ), patch(
            'books.commerce_api_views.Cart.objects',
            cart_manager,
        ), patch.object(
            Order,
            'objects',
            order_manager,
        ), patch.object(
            Payment,
            'objects',
            payment_manager,
        ):
            with self.assertRaisesMessage(
                ValidationError,
                'Giỏ hàng không còn hoạt động; hãy tải lại giỏ hàng.',
            ):
                CheckoutView.post.__wrapped__(CheckoutView(), request)

        cart_manager.select_for_update.assert_called_once()
        checkout_manager.create.assert_not_called()
        order_manager.create.assert_not_called()
        payment_manager.create.assert_not_called()


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
                'average_rating',
                'review_count',
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
            cloudinary_public_id=None,
            is_primary=True,
            sort_order=0,
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
            identifiers=SimpleNamespace(all=lambda: []),
        )
        book = SimpleNamespace(
            id=12,
            book_edition=edition,
            status='AVAILABLE',
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
                faculty_id=None,
                faculty=None,
                major_id=None,
                major=None,
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
            listing_reviews=[],
        )
        payload = lend_listing_payload(listing)
        self.assertEqual(payload['primary_image'], image.image_url)
        self.assertEqual(
            payload['images'],
            [{
                'id': image.id,
                'image_url': image.image_url,
                'cloudinary_public_id': image.cloudinary_public_id,
                'is_primary': True,
                'sort_order': 0,
            }],
        )
        self.assertEqual(payload['condition_status'], 'good')
        self.assertEqual(payload['status'], 'ACTIVE')
        self.assertEqual(payload['book']['status'], 'available')
        self.assertEqual(payload['subject']['code'], 'PHY101')
        self.assertEqual(
            payload['book']['seller']['university']['name'],
            'Example University',
        )
        self.assertEqual(payload['buying_intent_count'], 4)
        for listing_status, book_status, expected_status in (
            ('ACTIVE', 'AVAILABLE', 'available'),
            ('RESERVED', 'RESERVED', 'reserved'),
            ('ON_LOAN', 'ON_LOAN', 'on_loan'),
            ('EXPIRED', 'AVAILABLE', 'hidden'),
        ):
            with self.subTest(listing_status=listing_status, book_status=book_status):
                listing.status = listing_status
                book.status = book_status
                self.assertEqual(
                    lend_listing_payload(listing)['book']['status'],
                    expected_status,
                )

    def test_public_catalog_newest_sort_prioritizes_approval_time(self):
        queryset = Mock()
        for method in ('filter', 'select_related', 'prefetch_related', 'annotate', 'order_by'):
            getattr(queryset, method).return_value = queryset
        paginator = Mock()
        paginator.paginate_queryset.return_value = []
        paginator.get_paginated_response.return_value = Response({})
        request = APIRequestFactory().get('/api/lend-listings/', {'sort': 'newest'})

        with patch(
            'books.commerce_api_views.LendListing.objects.filter',
            return_value=queryset,
        ), patch(
            'books.commerce_api_views.BookPagination',
            return_value=paginator,
        ), patch(
            'books.commerce_api_views.prefetch_book_reviews',
        ):
            response = LendListingListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        queryset.order_by.assert_called_once_with(
            F('published_at').desc(nulls_last=True),
            '-id',
            '-created_at',
        )


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
    def test_editing_published_sale_listing_requires_review_again(self):
        factory = APIRequestFactory()
        request = factory.patch('/api/sale-listings/44/', {'price': '120000'})
        request.user = SimpleNamespace(id=7, is_authenticated=True)
        request.data = {'price': '120000'}
        listing = SimpleNamespace(
            id=44,
            pk=44,
            seller_id=7,
            status='ACTIVE',
            published_at=timezone.now(),
            updated_at=None,
            price=Decimal('100000'),
            book=SimpleNamespace(status='AVAILABLE'),
            save=Mock(),
        )
        listing_queryset = Mock()
        listing_queryset.return_value.get.return_value = listing

        with patch(
            'books.sale_api_views.get_object_or_404',
            return_value=listing,
        ), patch(
            'books.sale_api_views.listing_queryset',
            listing_queryset,
        ), patch(
            'books.sale_api_views.sale_listing_payload',
            return_value={'id': 44, 'status': 'PENDING'},
        ):
            response = SaleListingDetailView.patch.__wrapped__(
                SaleListingDetailView(),
                request,
                listing_id=44,
            )

        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(listing.status, 'PENDING')
        self.assertIsNone(listing.published_at)
        listing.save.assert_called_once()

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


class PendingBookDetailAccessTests(SimpleTestCase):
    @patch('books.api_views.prefetch_book_reviews')
    @patch('books.api_views.BookSerializer')
    @patch('books.api_views.optimized_books_queryset')
    def test_owner_can_view_own_pending_book_detail(
        self,
        optimized_queryset,
        serializer_class,
        prefetch_reviews,
    ):
        user = SimpleNamespace(id=10, is_authenticated=True)
        book = SimpleNamespace(id=32)
        queryset = Mock()
        queryset.filter.return_value = queryset
        queryset.first.return_value = book
        optimized_queryset.return_value = queryset
        serializer_class.return_value.data = {'id': book.id, 'images': []}
        request = APIRequestFactory().get('/api/books/32/')
        force_authenticate(request, user=user)

        response = BookDetailView.as_view()(request, pk=book.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'id': book.id, 'images': []})
        optimized_queryset.assert_called_once_with(include_history=True)
        queryset.filter.assert_called_once_with(
            owner_id=user.id,
            status='AVAILABLE',
            sale_listings__status='PENDING',
            pk=book.id,
        )


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
                'borrow',
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
            expires_at=now + timedelta(days=1),
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

    def test_rejected_pending_borrow_reopens_unexpired_listing(self):
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
            book_id=5,
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
            expires_at=now + timedelta(days=1),
            updated_at=None,
            save=Mock(),
        )
        reservation_manager = Mock()
        reservation_manager.select_for_update.return_value.get.return_value = reservation
        book_manager = Mock()
        book_manager.select_for_update.return_value.get.return_value = book
        lend_manager = Mock()
        lend_manager.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = listing

        with patch.object(BookReservation, 'objects', reservation_manager), patch(
            'books.services.Book.objects',
            book_manager,
        ), patch('books.services.LendListing.objects', lend_manager), patch(
            'books.services._notify',
        ):
            rejected = transition_reservation.__wrapped__(
                reservation.id,
                SimpleNamespace(id=7),
                'reject',
            )

        self.assertEqual(rejected.status, 'REJECTED')
        self.assertEqual(listing.status, 'ACTIVE')
        self.assertEqual(book.status, 'AVAILABLE')

    def test_return_does_not_reopen_an_expired_lend_listing(self):
        now = timezone.now()
        book = SimpleNamespace(
            id=5,
            status='ON_LOAN',
            updated_at=None,
            sale_listings=Mock(),
            save=Mock(),
        )
        reservation = SimpleNamespace(
            id=14,
            book_id=5,
            book=book,
            status='CONFIRMED',
            expires_at=now + timedelta(hours=1),
            owner_id=7,
            requester_id=8,
            updated_at=None,
            save=Mock(),
        )
        listing = SimpleNamespace(
            status='ON_LOAN',
            expires_at=now - timedelta(seconds=1),
            updated_at=None,
            save=Mock(),
        )
        reservation_manager = Mock()
        reservation_manager.select_for_update.return_value.get.return_value = reservation
        book_manager = Mock()
        book_manager.select_for_update.return_value.get.return_value = book
        lend_manager = Mock()
        lend_manager.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = listing

        with patch.object(BookReservation, 'objects', reservation_manager), patch(
            'books.services.Book.objects',
            book_manager,
        ), patch('books.services.LendListing.objects', lend_manager), patch(
            'books.services._notify',
        ):
            completed = transition_reservation.__wrapped__(
                reservation.id,
                SimpleNamespace(id=8),
                'complete',
            )

        self.assertEqual(completed.status, 'COMPLETED')
        self.assertEqual(listing.status, 'EXPIRED')
        self.assertEqual(book.status, 'AVAILABLE')

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
        serializer = BookRequestInputSerializer(data={
            'request_type': 'BUY',
            'title_keyword': 'Biology',
            'status': 'CANCELLED',
            'user_id': 99,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('status', serializer.validated_data)
        self.assertNotIn('user', serializer.validated_data)

    def test_request_can_save_a_future_planned_date_separately_from_expiry(self):
        planned_at = timezone.now() + timedelta(days=5)
        expires_at = planned_at + timedelta(days=2)
        serializer = BookRequestInputSerializer(data={
            'request_type': 'BUY',
            'title_keyword': 'Calculus I',
            'planned_at': planned_at.isoformat(),
            'expires_at': expires_at.isoformat(),
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['planned_at'], planned_at)
        self.assertEqual(serializer.validated_data['expires_at'], expires_at)

    def test_request_dates_reject_past_plans_and_expiry_before_plan(self):
        now = timezone.now()
        for planned_at, expires_at, expected_field in (
            (now - timedelta(days=1), now + timedelta(days=1), 'planned_at'),
            (now + timedelta(days=2), now + timedelta(days=1), 'expires_at'),
        ):
            with self.subTest(expected_field=expected_field):
                serializer = BookRequestInputSerializer(data={
                    'request_type': 'SELL_INTENT',
                    'title_keyword': 'Calculus I',
                    'planned_at': planned_at.isoformat(),
                    'expires_at': expires_at.isoformat(),
                })
                self.assertFalse(serializer.is_valid())
                self.assertIn(expected_field, serializer.errors)

    def test_patch_unrelated_fields_is_allowed_when_existing_plan_is_past(self):
        request = SimpleNamespace(
            request_type='BUY',
            book_work=None,
            category=None,
            title_keyword='Calculus I',
            budget_max=None,
            asking_price=None,
            planned_at=timezone.now() - timedelta(days=1),
            expires_at=None,
        )
        serializer = BookRequestInputSerializer(
            request,
            data={'description': 'Updated details'},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_editing_request_title_preserves_or_clears_book_work_correctly(self):
        request = SimpleNamespace(
            request_type='BUY',
            book_work=SimpleNamespace(id=12),
            category=None,
            title_keyword='Calculus I',
            budget_max=None,
            asking_price=None,
            planned_at=None,
            expires_at=None,
        )
        unchanged = BookRequestInputSerializer(
            request,
            data={'title_keyword': 'Calculus I'},
            partial=True,
        )
        changed = BookRequestInputSerializer(
            request,
            data={'title_keyword': 'Linear Algebra'},
            partial=True,
        )

        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        self.assertNotIn('book_work', unchanged.validated_data)
        self.assertTrue(changed.is_valid(), changed.errors)
        self.assertIsNone(changed.validated_data['book_work'])

    def test_request_payload_includes_planned_date_and_same_intent_count(self):
        planned_at = timezone.now() + timedelta(days=4)
        item = SimpleNamespace(
            id=1,
            user_id=10,
            request_type='BUY',
            book_work_id=None,
            category_id=None,
            title_keyword='Calculus I',
            description='',
            budget_max=None,
            asking_price=None,
            currency=None,
            condition_preference=None,
            status='OPEN',
            planned_at=planned_at,
            expires_at=None,
            same_intent_count=3,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        payload = request_payload(item)

        self.assertEqual(payload['planned_at'], planned_at)
        self.assertEqual(payload['same_intent_count'], 3)


class BookRequestInterestResponseTests(SimpleTestCase):
    def test_new_interest_sends_a_private_intro_and_notifies_request_owner(self):
        factory = APIRequestFactory()
        responder = SimpleNamespace(id=22, full_name='Responder')
        request = factory.post(
            '/api/book-requests/41/interests/',
            {'note': 'I have the 2025 edition.'},
            format='json',
        )
        force_authenticate(request, user=responder)
        view = BookRequestInterestView()
        api_request = view.initialize_request(request)
        owner = SimpleNamespace(id=11, full_name='Request owner')
        book_request = SimpleNamespace(
            id=41,
            user_id=owner.id,
            user=owner,
            status='OPEN',
            expires_at=None,
            request_type='BUY',
            book_work_id=None,
            title_keyword='Calculus I',
        )
        interest = SimpleNamespace(id=51, status='ACTIVE', note='I have the 2025 edition.')
        conversation = Mock(id=61, updated_at=None)

        with patch(
            'books.request_api_views.BookRequest.objects.select_for_update',
            return_value=Mock(),
        ), patch(
            'books.request_api_views.get_object_or_404',
            return_value=book_request,
        ), patch(
            'books.request_api_views.RequestInterest.objects.get_or_create',
            return_value=(interest, True),
        ), patch(
            'books.request_api_views.get_or_create_private_conversation',
            return_value=(conversation, True),
        ), patch(
            'books.request_api_views.Message.objects.create',
        ) as create_message, patch(
            'books.request_api_views.create_notification',
        ) as create_notification:
            response = BookRequestInterestView.post.__wrapped__(
                view,
                api_request,
                request_id=book_request.id,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['conversation_id'], conversation.id)
        create_message.assert_called_once()
        self.assertEqual(
            create_message.call_args.kwargs['content'],
            'Mình có thông tin sách phù hợp với yêu cầu “Calculus I”.\n'
            'I have the 2025 edition.',
        )
        create_notification.assert_called_once()
        self.assertEqual(
            create_notification.call_args.kwargs['entity_id'],
            conversation.id,
        )


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
            order_type='SALE',
            status='PENDING_PAYMENT',
            subtotal=Decimal('125.5000'),
            total_amount=Decimal('138.0500'),
            pricing_snapshot={},
            currency='VND',
            checkout_group=SimpleNamespace(id=4),
            updated_at=None,
            save=Mock(),
        )
        payment = SimpleNamespace(
            id=71,
            order_id=order.id,
            amount=Decimal('125.5000'),
            payment_method='CARD',
            provider='fake',
            provider_transaction_code='fake_ref',
            platform_fee_rate=Decimal('0'),
            platform_fee=Decimal('0'),
            seller_amount=Decimal('125.5000'),
            currency='VND',
            status='PENDING',
            paid_at=None,
            created_at=None,
            updated_at=None,
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
            'books.commerce_api_views.Order.objects.select_for_update',
        ) as order_lock, patch(
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
        self.assertEqual(
            values['seller_amount'],
            values['amount'] - values['platform_fee'],
        )
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
        for current, target in (
            ('FAILED', 'PAID'),
            ('CANCELLED', 'PAID'),
            ('REFUNDED', 'PAID'),
        ):
            with self.subTest(current=current, target=target):
                with self.assertRaises(ValidationError):
                    provider.transition(current, target)

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
        ), patch(
            'books.services.notify_order_status_changed',
        ), patch(
            'books.services.SaleOrderItem.objects.select_for_update',
        ) as sale_items:
            sale_items.return_value.filter.return_value.select_related.return_value = []
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
    def test_borrower_and_lender_cannot_manage_admin_shipping_transitions(self):
        for action in ('confirm', 'reject', 'ready', 'start', 'complete'):
            with self.subTest(action=action):
                request = APIRequestFactory().post(
                    f'/api/borrow-orders/18/{action}/',
                    {},
                    format='json',
                )
                force_authenticate(
                    request,
                    user=SimpleNamespace(id=10, is_authenticated=True),
                )
                response = BorrowOrderActionView.as_view()(
                    request,
                    borrow_order_id=18,
                    action=action,
                )
                self.assertEqual(response.status_code, 400)

    def test_rejecting_paid_borrow_order_creates_refund_request(self):
        lender = SimpleNamespace(id=10)
        book = SimpleNamespace(status='RESERVED', save=Mock())
        listing = SimpleNamespace(
            status='RESERVED',
            expires_at=None,
            updated_at=None,
            save=Mock(),
            book=book,
        )
        order = SimpleNamespace(
            id=24,
            status='CONFIRMED',
            updated_at=None,
            save=Mock(),
        )
        borrow = SimpleNamespace(
            id=18,
            status='PENDING',
            lender_id=lender.id,
            borrower_id=11,
            order=order,
            lend_listing=listing,
            updated_at=None,
            save=Mock(),
        )
        borrow_query = Mock()
        borrow_query.select_related.return_value = borrow_query
        borrow_query.get.return_value = borrow
        borrow_manager = Mock()
        borrow_manager.select_for_update.return_value = borrow_query
        payment = SimpleNamespace(
            id=31,
            status='PAID',
            amount=Decimal('75000.0000'),
            currency='VND',
            provider='online',
        )
        payment_query = Mock()
        payment_query.filter.return_value = [payment]
        payment_manager = Mock()
        payment_manager.select_for_update.return_value = payment_query
        refunds = Mock()
        refunds.aggregate.return_value = {'total': Decimal('0')}
        refund_query = Mock()
        refund_query.filter.return_value = refunds
        refund_manager = Mock()
        refund_manager.select_for_update.return_value = refund_query

        with patch('books.services.BorrowOrder.objects', borrow_manager), patch(
            'books.services.Payment.objects',
            payment_manager,
        ), patch(
            'books.services.Refund.objects',
            refund_manager,
        ), patch('books.services._notify'):
            transition_borrow_order.__wrapped__(18, lender, 'reject')

        self.assertEqual(borrow.status, 'REJECTED')
        self.assertEqual(order.status, 'CANCELLED')
        self.assertEqual(listing.status, 'ACTIVE')
        self.assertEqual(book.status, 'AVAILABLE')
        refund_manager.create.assert_called_once()
        refund = refund_manager.create.call_args.kwargs
        self.assertEqual(refund['borrow_order'], borrow)
        self.assertEqual(refund['amount'], payment.amount)
        self.assertEqual(refund['status'], 'REQUESTED')

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


class BorrowReturnFlowTests(SimpleTestCase):
    def test_return_request_url_precedes_generic_borrow_action_route(self):
        match = resolve('/api/borrow-orders/7/return-request/')
        self.assertIs(
            match.func.view_class,
            BorrowOrderReturnRequestView,
        )

    def _borrow_order(self, *, status='ACTIVE', return_status=None):
        book = SimpleNamespace(
            id=5,
            status='ON_LOAN',
            updated_at=None,
            save=Mock(),
        )
        listing = SimpleNamespace(
            id=6,
            book_id=book.id,
            book=book,
            status='ON_LOAN',
            expires_at=None,
            updated_at=None,
            save=Mock(),
        )
        order = SimpleNamespace(
            id=4,
            status='PAID',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        return SimpleNamespace(
            id=7,
            order_id=order.id,
            order=order,
            lend_listing_id=listing.id,
            lend_listing=listing,
            borrower_id=12,
            lender_id=13,
            status=status,
            return_status=return_status,
            return_tracking_code=None,
            return_method=None,
            return_requested_by=None,
            return_requested_at=None,
            return_approved_at=None,
            return_notes=None,
            actual_return_at=None,
            updated_at=None,
            save=Mock(),
        )

    def _locked_borrow_manager(self, borrow):
        queryset = Mock()
        queryset.select_related.return_value = queryset
        queryset.get.return_value = borrow
        manager = Mock()
        manager.select_for_update.return_value = queryset
        return manager

    @staticmethod
    def _drf_request(view_class, request, user):
        force_authenticate(request, user=user)
        return view_class().initialize_request(request)

    def test_return_request_creates_one_return_shipment_for_borrower(self):
        borrow = self._borrow_order()
        shipment = SimpleNamespace(
            id=23,
            status='PENDING',
            carrier='Local delivery',
            tracking_code='RET-123',
        )
        factory = APIRequestFactory()
        request = factory.post(
            '/api/borrow-orders/7/return-request/',
            {
                'return_method': 'DELIVERY',
                'carrier': 'Local delivery',
                'return_tracking_code': 'RET-123',
                'return_notes': 'Leave with owner',
            },
            format='json',
        )
        request = self._drf_request(
            BorrowOrderReturnRequestView,
            request,
            SimpleNamespace(id=borrow.borrower_id, is_authenticated=True),
        )

        with patch(
            'books.commerce_api_views.BorrowOrder.objects',
            self._locked_borrow_manager(borrow),
        ), patch('books.commerce_api_views.get_object_or_404', return_value=borrow), patch(
            'books.commerce_api_views.mark_overdue_borrow_orders',
        ), patch(
            'books.commerce_api_views.Shipment.objects',
        ) as shipment_manager, patch(
            'books.commerce_api_views.ShipmentTracking.objects',
        ) as tracking_manager:
            with patch(
                'books.commerce_api_views.notify_borrow_order_parties',
            ) as notify_borrow:
                shipment_manager.filter.return_value.exists.return_value = False
                shipment_manager.create.return_value = shipment
                response = BorrowOrderReturnRequestView.post.__wrapped__(
                    BorrowOrderReturnRequestView(),
                    request,
                    borrow_order_id=borrow.id,
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['shipment']['direction'], 'BORROWER_TO_OWNER')
        self.assertEqual(borrow.status, 'RETURN_REQUESTED')
        self.assertEqual(borrow.return_status, 'SHIPPING')
        self.assertEqual(borrow.return_tracking_code, 'RET-123')
        shipment_manager.create.assert_called_once()
        self.assertEqual(
            shipment_manager.create.call_args.kwargs['order'],
            borrow.order,
        )
        self.assertEqual(
            shipment_manager.create.call_args.kwargs['shipping_fee'],
            Decimal('0'),
        )
        self.assertEqual(
            tracking_manager.create.call_args.kwargs['status'],
            'PENDING',
        )
        notify_borrow.assert_called_once_with(
            borrow,
            title='Yêu cầu trả sách đang được vận chuyển',
            content=(
                f'Người mượn đã tạo yêu cầu trả cho phiếu #{borrow.id}. '
                'Admin sẽ cập nhật trạng thái vận chuyển và xác nhận khi nhận lại sách.'
            ),
            recipient_ids=(borrow.lender_id,),
        )

    def test_owner_and_outsider_cannot_create_return(self):
        for user_id in (13, 99):
            with self.subTest(user_id=user_id):
                borrow = self._borrow_order()
                request = APIRequestFactory().post(
                    '/api/borrow-orders/7/return-request/',
                    {
                        'return_method': 'DELIVERY',
                        'carrier': 'Local delivery',
                        'return_tracking_code': 'RET-123',
                    },
                    format='json',
                )
                request = self._drf_request(
                    BorrowOrderReturnRequestView,
                    request,
                    SimpleNamespace(id=user_id, is_authenticated=True),
                )
                with patch(
                    'books.commerce_api_views.get_object_or_404',
                    return_value=borrow,
                ), patch(
                    'books.commerce_api_views.mark_overdue_borrow_orders',
                ), patch(
                    'books.commerce_api_views.Shipment.objects.create',
                ) as create_shipment:
                    with self.assertRaises(PermissionDenied):
                        BorrowOrderReturnRequestView.post.__wrapped__(
                            BorrowOrderReturnRequestView(),
                            request,
                            borrow_order_id=borrow.id,
                        )
                create_shipment.assert_not_called()

    def test_duplicate_return_request_does_not_create_another_shipment(self):
        borrow = self._borrow_order(status='RETURN_REQUESTED', return_status='SHIPPING')
        request = APIRequestFactory().post(
            '/api/borrow-orders/7/return-request/',
            {
                'return_method': 'DELIVERY',
                'carrier': 'Local delivery',
                'return_tracking_code': 'RET-123',
            },
            format='json',
        )
        request = self._drf_request(
            BorrowOrderReturnRequestView,
            request,
            SimpleNamespace(id=borrow.borrower_id, is_authenticated=True),
        )
        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=borrow,
        ), patch(
            'books.commerce_api_views.mark_overdue_borrow_orders',
        ), patch(
            'books.commerce_api_views.Shipment.objects.create',
        ) as create_shipment:
            with self.assertRaises(ValidationError):
                BorrowOrderReturnRequestView.post.__wrapped__(
                    BorrowOrderReturnRequestView(),
                    request,
                    borrow_order_id=borrow.id,
                )
        create_shipment.assert_not_called()

    def test_admin_manages_borrow_return_tracking_instead_of_borrower(self):
        borrow = self._borrow_order(status='RETURN_REQUESTED', return_status='SHIPPING')
        borrow.return_tracking_code = 'RET-123'
        shipment = SimpleNamespace(
            id=23,
            order_id=borrow.order_id,
            tracking_code='RET-123',
            status='IN_TRANSIT',
        )
        manager = Mock()
        manager.select_for_update.return_value.filter.return_value.first.return_value = borrow
        request = APIRequestFactory().post(
            '/api/shipments/23/tracking/',
            {'status': 'DELIVERED'},
            format='json',
        )
        request = self._drf_request(
            ShipmentTrackingCreateView,
            request,
            SimpleNamespace(id=borrow.borrower_id, is_authenticated=True),
        )

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.commerce_api_views.BorrowOrder.objects',
            manager,
        ), patch(
            'books.commerce_api_views.update_shipment_status',
        ) as update_status:
            with self.assertRaises(PermissionDenied):
                ShipmentTrackingCreateView.post.__wrapped__(
                    ShipmentTrackingCreateView(),
                    request,
                    shipment_id=shipment.id,
                )

        self.assertEqual(shipment.status, 'IN_TRANSIT')
        self.assertEqual(borrow.status, 'RETURN_REQUESTED')
        update_status.assert_not_called()

    def test_borrower_cannot_update_any_borrow_return_tracking_status(self):
        borrow = self._borrow_order(status='RETURN_REQUESTED', return_status='SHIPPING')
        borrow.return_tracking_code = 'RET-123'
        shipment = SimpleNamespace(
            id=23,
            order_id=borrow.order_id,
            tracking_code='RET-123',
            status='PENDING',
        )
        factory = APIRequestFactory()
        for tracking_status in ('PICKED_UP', 'IN_TRANSIT', 'DELIVERED'):
            with self.subTest(status=tracking_status):
                request = self._drf_request(
                    ShipmentTrackingCreateView,
                    factory.post(
                        '/api/shipments/23/tracking/',
                        {'status': tracking_status},
                        format='json',
                    ),
                    SimpleNamespace(id=borrow.borrower_id, is_authenticated=True),
                )
                borrow_manager = Mock()
                borrow_manager.select_for_update.return_value.filter.return_value.first.return_value = borrow
                with patch(
                    'books.commerce_api_views.get_object_or_404',
                    return_value=shipment,
                ), patch(
                    'books.commerce_api_views.BorrowOrder.objects',
                    borrow_manager,
                ), patch(
                    'books.commerce_api_views.ShipmentTracking.objects.create',
                ) as create_event:
                    with self.assertRaises(PermissionDenied):
                        ShipmentTrackingCreateView.post.__wrapped__(
                            ShipmentTrackingCreateView(),
                            request,
                            shipment_id=shipment.id,
                        )
                create_event.assert_not_called()
                self.assertEqual(shipment.status, 'PENDING')

        self.assertEqual(borrow.status, 'RETURN_REQUESTED')
        self.assertEqual(borrow.return_status, 'SHIPPING')

    def test_borrower_cannot_update_return_shipment_status(self):
        borrow = self._borrow_order(status='RETURN_REQUESTED', return_status='SHIPPING')
        borrow.return_tracking_code = 'RET-123'
        shipment = SimpleNamespace(
            id=23,
            order_id=borrow.order_id,
            tracking_code='RET-123',
            status='PENDING',
            tracking_events=Mock(),
        )
        manager = Mock()
        manager.select_for_update.return_value.filter.return_value.first.return_value = borrow
        request = self._drf_request(
            ShipmentTrackingCreateView,
            APIRequestFactory().post(
                '/api/shipments/23/tracking/',
                {'status': 'DELIVERED'},
                format='json',
            ),
            SimpleNamespace(id=borrow.borrower_id, is_authenticated=True),
        )
        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.commerce_api_views.BorrowOrder.objects',
            manager,
        ), patch(
            'books.commerce_api_views.update_shipment_status',
            update_shipment_status.__wrapped__,
        ), patch(
            'books.commerce_api_views.ShipmentTracking.objects.create',
        ) as create_event:
            with self.assertRaises(PermissionDenied):
                ShipmentTrackingCreateView.post.__wrapped__(
                    ShipmentTrackingCreateView(),
                    request,
                    shipment_id=shipment.id,
                )
        create_event.assert_not_called()
        self.assertEqual(borrow.status, 'RETURN_REQUESTED')

    def test_lender_cannot_update_outbound_borrow_shipment(self):
        borrow = self._borrow_order(status='ACTIVE')
        shipment = SimpleNamespace(
            id=23,
            order_id=borrow.order_id,
            tracking_code=None,
            status='SHIPPED',
            order=SimpleNamespace(seller_id=None),
            shipped_at=timezone.now(),
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        manager = Mock()
        manager.select_for_update.return_value.filter.return_value.first.return_value = borrow
        request = self._drf_request(
            ShipmentTrackingCreateView,
            APIRequestFactory().post(
                '/api/shipments/23/tracking/',
                {'status': 'IN_TRANSIT'},
                format='json',
            ),
            SimpleNamespace(id=borrow.lender_id, is_authenticated=True),
        )
        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.commerce_api_views.BorrowOrder.objects',
            manager,
        ), patch(
            'books.commerce_api_views.update_shipment_status',
        ) as update_status:
            with self.assertRaises(PermissionDenied):
                ShipmentTrackingCreateView.post.__wrapped__(
                    ShipmentTrackingCreateView(),
                    request,
                    shipment_id=shipment.id,
                )

        self.assertEqual(borrow.status, 'ACTIVE')
        self.assertIsNone(borrow.return_status)
        self.assertEqual(shipment.status, 'SHIPPED')
        update_status.assert_not_called()

    def test_only_lender_can_confirm_delivered_return_and_reopen_inventory(self):
        borrow = self._borrow_order(status='RETURNED', return_status='DELIVERED')
        borrow.return_tracking_code = 'RET-123'
        manager = self._locked_borrow_manager(borrow)
        with patch('books.services.BorrowOrder.objects', manager), patch(
            'books.services.Shipment.objects.filter',
        ) as shipments, patch('books.services._notify'):
            shipments.return_value.exists.return_value = True
            result = transition_borrow_order.__wrapped__(
                borrow.id,
                SimpleNamespace(id=borrow.lender_id),
                'complete',
            )

        self.assertIs(result, borrow)
        self.assertEqual(borrow.status, 'COMPLETED')
        self.assertEqual(borrow.return_status, 'COMPLETED')
        self.assertEqual(borrow.order.status, 'COMPLETED')
        self.assertEqual(borrow.lend_listing.status, 'ACTIVE')
        self.assertEqual(borrow.lend_listing.book.status, 'AVAILABLE')

    def test_borrower_cannot_confirm_and_owner_cannot_complete_undelivered_return(self):
        for user_id, status, return_status, shipment_exists in (
            (12, 'RETURNED', 'DELIVERED', True),
            (13, 'RETURN_REQUESTED', 'SHIPPING', False),
        ):
            with self.subTest(user_id=user_id, status=status):
                borrow = self._borrow_order(
                    status=status,
                    return_status=return_status,
                )
                borrow.return_tracking_code = 'RET-123'
                with patch(
                    'books.services.BorrowOrder.objects',
                    self._locked_borrow_manager(borrow),
                ), patch(
                    'books.services.Shipment.objects.filter',
                ) as shipments:
                    shipments.return_value.exists.return_value = shipment_exists
                    with self.assertRaises((PermissionDenied, ValidationError)):
                        transition_borrow_order.__wrapped__(
                            borrow.id,
                            SimpleNamespace(id=user_id),
                            'complete',
                        )
                self.assertIn(borrow.status, ('RETURNED', 'RETURN_REQUESTED'))
                borrow.lend_listing.save.assert_not_called()
                borrow.lend_listing.book.save.assert_not_called()

    def test_return_request_requires_supported_shipping_details(self):
        serializer = BorrowReturnInputSerializer(data={
            'return_method': 'PICKUP',
            'carrier': '',
            'return_tracking_code': '',
        })
        self.assertFalse(serializer.is_valid())
