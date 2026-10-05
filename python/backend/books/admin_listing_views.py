from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin

from .models import Book, BookImage, LendListing, SaleListing
from .pagination import BookPagination


LISTING_TYPES = {
    'sale': (SaleListing, 'seller', 'SALE'),
    'borrow': (LendListing, 'lender', 'BORROW'),
}


def _listing_type(value):
    try:
        return LISTING_TYPES[value.lower()]
    except (AttributeError, KeyError) as exc:
        raise ValidationError({
            'listing_type': 'Loại tin đăng không hợp lệ.',
        }) from exc


def _listing_payload(listing, owner_field, listing_type):
    book = listing.book
    edition = book.book_edition
    work = edition.book_work
    category = work.category
    language = edition.language
    owner = getattr(listing, owner_field)
    images = getattr(book, 'moderation_images', [])
    return {
        'id': listing.id,
        'listing_type': listing_type,
        'title': listing.title,
        'description': listing.description,
        'status': listing.status,
        'price': str(
            listing.price if listing_type == 'SALE' else listing.rental_fee,
        ),
        'currency': listing.currency,
        'created_at': listing.created_at,
        'owner': {
            'id': owner.id,
            'name': owner.full_name,
            'email': owner.email,
        },
        'book': {
            'id': book.id,
            'title': work.title,
            'condition_status': book.condition_status,
            'condition_description': book.condition_description,
            'author': work.author_name,
            'publisher': edition.publisher_name,
            'edition': edition.edition_name,
            'publication_year': edition.publication_year,
            'category': category.name if category else None,
            'language': language.name if language else None,
            'images': [image.image_url for image in images],
        },
    }


class AdminListingModerationListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, listing_type):
        model, owner_field, payload_type = _listing_type(listing_type)
        status_value = request.query_params.get('status', 'PENDING').strip().upper()
        valid_statuses = {value for value, _label in model.STATUS_CHOICES}
        if status_value and status_value not in valid_statuses:
            raise serializers.ValidationError({
                'status': 'Trạng thái tin đăng không hợp lệ.',
            })

        queryset = model.objects.select_related(
            f'{owner_field}',
            'book__book_edition__book_work__category',
            'book__book_edition__language',
        ).prefetch_related(
            Prefetch(
                'book__images',
                queryset=BookImage.objects.filter(is_primary=True).order_by(
                    'sort_order', 'id',
                ),
                to_attr='moderation_images',
            ),
        ).order_by('-created_at', '-id')
        if status_value:
            queryset = queryset.filter(status=status_value)
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(**{f'{owner_field}__email__icontains': search})
                | Q(**{f'{owner_field}__full_name__icontains': search})
                | Q(book__book_edition__book_work__title__icontains=search)
                | Q(book__book_edition__book_work__author_name__icontains=search)
            )

        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        results = [
            _listing_payload(listing, owner_field, payload_type)
            for listing in page
        ]
        return paginator.get_paginated_response(results)


class AdminListingModerationActionView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, listing_type, listing_id):
        model, _owner_field, _payload_type = _listing_type(listing_type)
        action = request.data.get('action')
        if action not in ('APPROVE', 'REJECT'):
            raise serializers.ValidationError({
                'action': 'Chỉ chấp nhận APPROVE hoặc REJECT.',
            })

        listing = get_object_or_404(
            model.objects.select_for_update(),
            pk=listing_id,
        )
        if listing.status != 'PENDING':
            raise ValidationError({
                'status': 'Chỉ tin đang chờ duyệt mới có thể được xử lý.',
            })

        if action == 'APPROVE':
            book = Book.objects.select_for_update().get(pk=listing.book_id)
            if book.status != 'AVAILABLE':
                raise ValidationError({
                    'book': 'Chỉ có thể duyệt tin khi sách còn khả dụng.',
                })
            other_sale = SaleListing.objects.filter(
                book_id=book.id,
                status__in=('PENDING', 'ACTIVE', 'RESERVED', 'SOLD'),
            )
            other_borrow = LendListing.objects.filter(
                book_id=book.id,
                status__in=('PENDING', 'ACTIVE', 'RESERVED', 'ON_LOAN'),
            )
            if model is SaleListing:
                other_sale = other_sale.exclude(pk=listing.pk)
            else:
                other_borrow = other_borrow.exclude(pk=listing.pk)
            other_sale = other_sale.exists()
            other_borrow = other_borrow.exists()
            if other_sale or other_borrow:
                raise ValidationError({
                    'book': 'Sách đã có tin đăng đang hoạt động.',
                })

        now = timezone.now()
        listing.status = 'ACTIVE' if action == 'APPROVE' else 'REJECTED'
        listing.published_at = now if action == 'APPROVE' else None
        listing.updated_at = now
        listing.save(update_fields=('status', 'published_at', 'updated_at'))
        return Response({
            'id': listing.id,
            'status': listing.status,
            'action': action,
        })
