from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Book, LendListing, SaleListing
from .admin_listing_views import (
    AdminListingModerationActionView,
    AdminListingModerationListView,
    LISTING_TYPES,
    _listing_payload,
    _listing_type,
)


class AdminListingModerationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = SimpleNamespace(
            id=1,
            is_authenticated=True,
            role='ADMIN',
        )

    def test_moderation_routes_and_listing_types_cover_sale_and_borrow(self):
        self.assertEqual(_listing_type('sale'), LISTING_TYPES['sale'])
        self.assertEqual(_listing_type('borrow'), LISTING_TYPES['borrow'])
        self.assertEqual(
            resolve('/api/admin/dashboard/listings/sale/').url_name,
            'admin-dashboard-listings',
        )
        self.assertEqual(
            resolve(
                '/api/admin/dashboard/listings/borrow/12/moderation/',
            ).url_name,
            'admin-dashboard-listing-moderation',
        )

    def test_invalid_listing_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            _listing_type('other')

    def test_payload_contains_owner_book_and_listing_details(self):
        owner = SimpleNamespace(id=7, full_name='Seller', email='seller@example.com')
        book = SimpleNamespace(
            id=14,
            condition_status='GOOD',
            condition_description='Clean pages',
            book_edition=SimpleNamespace(
                edition_name='Third edition',
                publication_year=2024,
                publisher_name='Publisher',
                language=SimpleNamespace(name='Vietnamese'),
                book_work=SimpleNamespace(
                    title='Textbook',
                    author_name='Author',
                    category=SimpleNamespace(name='Engineering'),
                ),
            ),
            moderation_images=[SimpleNamespace(image_url='https://example.com/cover.jpg')],
        )
        listing = SimpleNamespace(
            id=12,
            title='Textbook listing',
            description='Description',
            status='PENDING',
            price='100000.0000',
            currency='VND',
            created_at='2026-10-05T00:00:00Z',
            seller=owner,
            book=book,
        )

        payload = _listing_payload(listing, 'seller', 'SALE')

        self.assertEqual(payload['listing_type'], 'SALE')
        self.assertEqual(payload['owner']['email'], 'seller@example.com')
        self.assertEqual(payload['book']['title'], 'Textbook')
        self.assertEqual(payload['book']['images'], ['https://example.com/cover.jpg'])

    def test_non_admin_cannot_access_moderation_list_or_action(self):
        student = SimpleNamespace(
            id=2,
            is_authenticated=True,
            role='STUDENT',
        )
        requests = (
            (
                AdminListingModerationListView.as_view(),
                self.factory.get('/api/admin/dashboard/listings/sale/'),
                {'listing_type': 'sale'},
            ),
            (
                AdminListingModerationActionView.as_view(),
                self.factory.patch(
                    '/api/admin/dashboard/listings/sale/12/moderation/',
                    {'action': 'APPROVE'},
                    format='json',
                ),
                {'listing_type': 'sale', 'listing_id': 12},
            ),
        )
        for view, request, kwargs in requests:
            with self.subTest(view=view):
                force_authenticate(request, user=student)
                response = view(request, **kwargs)
                self.assertEqual(response.status_code, 403)

    def test_reject_action_updates_only_pending_listing(self):
        listing = SimpleNamespace(
            id=12,
            status='PENDING',
            published_at=None,
            updated_at=None,
            save=Mock(),
        )
        raw_request = self.factory.patch(
            '/api/admin/dashboard/listings/sale/12/moderation/',
            {'action': 'REJECT'},
            format='json',
        )
        force_authenticate(raw_request, user=self.admin)
        view = AdminListingModerationActionView()
        request = view.initialize_request(raw_request)

        with patch(
            'books.admin_listing_views.get_object_or_404',
            return_value=listing,
        ):
            response = AdminListingModerationActionView.patch.__wrapped__(
                view,
                request,
                'sale',
                12,
            )

        self.assertEqual(response.data['status'], 'REJECTED')
        self.assertIsNone(listing.published_at)
        listing.save.assert_called_once_with(
            update_fields=('status', 'published_at', 'updated_at'),
        )

    def test_approve_action_publishes_available_sale_listing(self):
        book = SimpleNamespace(id=14, status='AVAILABLE')
        listing = SimpleNamespace(
            id=12,
            pk=12,
            book_id=14,
            status='PENDING',
            published_at=None,
            updated_at=None,
            save=Mock(),
        )
        raw_request = self.factory.patch(
            '/api/admin/dashboard/listings/sale/12/moderation/',
            {'action': 'APPROVE'},
            format='json',
        )
        force_authenticate(raw_request, user=self.admin)
        view = AdminListingModerationActionView()
        request = view.initialize_request(raw_request)
        book_queryset = Mock()
        book_queryset.get.return_value = book
        sale_queryset = Mock()
        sale_queryset.exclude.return_value.exists.return_value = False
        sale_queryset.exists.return_value = False
        borrow_queryset = Mock()
        borrow_queryset.exists.return_value = False

        with patch(
            'books.admin_listing_views.get_object_or_404',
            return_value=listing,
        ), patch.object(
            Book.objects,
            'select_for_update',
            return_value=book_queryset,
        ), patch.object(
            SaleListing.objects,
            'filter',
            return_value=sale_queryset,
        ), patch.object(
            LendListing.objects,
            'filter',
            return_value=borrow_queryset,
        ):
            response = AdminListingModerationActionView.patch.__wrapped__(
                view,
                request,
                'sale',
                12,
            )

        self.assertEqual(response.data['status'], 'ACTIVE')
        self.assertEqual(response.data['action'], 'APPROVE')
        self.assertIsNotNone(listing.published_at)
        listing.save.assert_called_once_with(
            update_fields=('status', 'published_at', 'updated_at'),
        )
