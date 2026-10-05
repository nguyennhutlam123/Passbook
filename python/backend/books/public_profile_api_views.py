from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from .category_taxonomy import BOOK_CATEGORY_SLUGS
from .models import (
    BookImage,
    BookWorkSubject,
    BorrowTerms,
    LendListing,
    SaleListing,
)
from .pagination import BookPagination


def _listing_queryset(listing_type, user_id, now):
    if listing_type == 'SALE':
        return SaleListing.objects.filter(
            seller_id=user_id,
            status='ACTIVE',
            book__status='AVAILABLE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        ).filter(
            Q(book__book_edition__book_work__category__isnull=True)
            | Q(
                book__book_edition__book_work__category__status='ACTIVE',
                book__book_edition__book_work__category__slug__in=BOOK_CATEGORY_SLUGS,
            ),
        ).select_related(
            'seller__university',
            'book__book_edition__book_work__category',
            'book__book_edition__language',
        ).prefetch_related(
            Prefetch(
                'book__images',
                queryset=BookImage.objects.filter(is_primary=True).order_by('id'),
                to_attr='public_primary_images',
            ),
            Prefetch(
                'book__book_edition__book_work__subject_links',
                queryset=BookWorkSubject.objects.filter(
                    is_primary=True,
                ).select_related('subject'),
                to_attr='primary_subject_links',
            ),
        ).order_by('-created_at', '-id')

    return LendListing.objects.filter(
        lender_id=user_id,
        status='ACTIVE',
        book__status='AVAILABLE',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).filter(
        Q(book__book_edition__book_work__category__isnull=True)
        | Q(
            book__book_edition__book_work__category__status='ACTIVE',
            book__book_edition__book_work__category__slug__in=BOOK_CATEGORY_SLUGS,
        ),
    ).select_related(
        'lender__university',
        'book__book_edition__book_work__category',
        'book__book_edition__language',
    ).prefetch_related(
        Prefetch(
            'book__images',
            queryset=BookImage.objects.filter(is_primary=True).order_by('id'),
            to_attr='public_primary_images',
        ),
        Prefetch(
            'book__book_edition__book_work__subject_links',
            queryset=BookWorkSubject.objects.filter(
                is_primary=True,
            ).select_related('subject'),
            to_attr='primary_subject_links',
        ),
        Prefetch(
            'borrow_terms',
            queryset=BorrowTerms.objects.only(
                'id',
                'lend_listing_id',
                'max_days',
                'deposit_required',
            ),
            to_attr='public_listing_terms',
        ),
    ).order_by('-created_at', '-id')


def _card_listing_payload(listing, listing_type):
    book = listing.book
    edition = book.book_edition
    work = edition.book_work
    subject_links = getattr(work, 'primary_subject_links', ())
    subject = subject_links[0].subject if subject_links else None
    images = getattr(book, 'public_primary_images', ())
    image = images[0] if images else None
    seller = listing.seller if listing_type == 'SALE' else listing.lender
    terms = getattr(listing, 'public_listing_terms', ())
    borrow_terms = (
        terms[0] if isinstance(terms, (tuple, list)) and terms
        else terms if terms else None
    )

    return {
        'id': book.id,
        'listing_id': listing.id,
        'listing_type': listing_type,
        'title': listing.title,
        'price': str(
            listing.price if listing_type == 'SALE' else listing.rental_fee,
        ),
        'deposit_amount': (
            str(listing.deposit_amount)
            if listing_type == 'BORROW' and listing.deposit_amount is not None
            else None
        ),
        'condition_status': book.condition_status,
        'condition_label': book.condition_label,
        'edition': edition.edition_name,
        'publication_year': edition.publication_year,
        'subject': (
            {'id': subject.id, 'name': subject.name, 'code': subject.code}
            if subject else None
        ),
        'category': (
            {'id': work.category_id, 'name': work.category.name}
            if work.category_id else None
        ),
        'primary_image': (
            {
                'id': image.id,
                'image_url': image.image_url,
                'is_primary': image.is_primary,
            }
            if image else None
        ),
        'seller': {
            'id': seller.id,
            'name': seller.full_name,
            'university': (
                {'id': seller.university_id, 'name': seller.university.name}
                if seller.university_id else None
            ),
        },
        'borrow_terms': (
            {
                'max_days': borrow_terms.max_days,
                'deposit_required': borrow_terms.deposit_required,
            }
            if borrow_terms else None
        ),
        'created_at': listing.created_at,
    }


class PublicUserListingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        get_object_or_404(
            User.objects.only('id'),
            pk=user_id,
            status='ACTIVE',
        )
        listing_type = request.query_params.get('type', 'ALL').upper()
        if listing_type not in ('ALL', 'SALE', 'BORROW'):
            raise serializers.ValidationError({
                'type': 'type phải là ALL, SALE hoặc BORROW.',
            })

        now = timezone.now()
        sale_queryset = _listing_queryset('SALE', user_id, now)
        borrow_queryset = _listing_queryset('BORROW', user_id, now)
        sale_count = sale_queryset.count()
        borrow_count = borrow_queryset.count()
        total_count = (
            sale_count if listing_type == 'SALE'
            else borrow_count if listing_type == 'BORROW'
            else sale_count + borrow_count
        )

        paginator = BookPagination()
        page_size = paginator.get_page_size(request)
        try:
            page_number = max(1, int(request.query_params.get(
                paginator.page_query_param,
                1,
            )))
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError({
                paginator.page_query_param: 'page phải là số nguyên dương.',
            }) from exc
        offset = (page_number - 1) * page_size
        fetch_limit = offset + page_size

        candidates = []
        if listing_type in ('ALL', 'SALE'):
            candidates.extend(
                (_card_listing_payload(row, 'SALE') for row in sale_queryset[:fetch_limit]),
            )
        if listing_type in ('ALL', 'BORROW'):
            candidates.extend(
                (_card_listing_payload(row, 'BORROW') for row in borrow_queryset[:fetch_limit]),
            )
        candidates.sort(
            key=lambda item: (item['created_at'], item['listing_id']),
            reverse=True,
        )
        results = candidates[offset:offset + page_size]

        query = request.query_params.copy()
        query['type'] = listing_type
        query['page_size'] = str(page_size)

        def page_url(number):
            params = query.copy()
            params[paginator.page_query_param] = str(number)
            return f'{request.build_absolute_uri(request.path)}?{params.urlencode()}'

        return Response({
            'count': total_count,
            'next': page_url(page_number + 1) if offset + page_size < total_count else None,
            'previous': page_url(page_number - 1) if page_number > 1 else None,
            'results': results,
            'sale_count': sale_count,
            'borrow_count': borrow_count,
        })
