from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Book,
    BookIdentifier,
    BookImage,
    BookWorkSubject,
    SaleListing,
)
from .pagination import BookPagination


class SaleListingInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1, required=False)
    title = serializers.CharField(max_length=500, required=False, allow_blank=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    price = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal('0.0001'),
        required=False,
    )
    status = serializers.ChoiceField(
        choices=('DRAFT', 'CLOSED'),
        required=False,
    )


def sale_listing_payload(listing, *, include_description=True):
    book = listing.book
    image = next(
        (image for image in getattr(book, 'primary_images', ()) if image.is_primary),
        None,
    )
    work = book.book_edition.book_work
    payload = {
        'id': listing.id,
        'book_id': listing.book_id,
        'title': listing.title,
        'price': str(listing.price),
        'currency': listing.currency,
        'status': listing.status,
        'seller': {
            'id': listing.seller_id,
            'name': listing.seller.full_name,
        },
        'book': {
            'condition_status': book.condition_label,
            'edition': book.book_edition.edition_name,
            'publication_year': book.book_edition.publication_year,
            'work_title': work.title,
        },
        'primary_image': image.image_url if image else None,
        'created_at': listing.created_at,
        'updated_at': listing.updated_at,
    }
    if include_description:
        payload['description'] = listing.description
    return payload


def listing_queryset(*, list_payload=False):
    listings = SaleListing.objects.all()
    images = BookImage.objects.filter(is_primary=True).order_by('id')
    if list_payload:
        listings = listings.only(
            'id',
            'book_id',
            'seller_id',
            'title',
            'price',
            'currency',
            'status',
            'created_at',
            'updated_at',
            'expires_at',
            'book__id',
            'book__condition_label',
            'book__book_edition_id',
            'book__book_edition__id',
            'book__book_edition__edition_name',
            'book__book_edition__publication_year',
            'book__book_edition__book_work_id',
            'book__book_edition__book_work__id',
            'book__book_edition__book_work__title',
            'seller__id',
            'seller__full_name',
        )
        images = images.only('id', 'book_id', 'image_url', 'is_primary')
    return (
        listings.select_related(
            'seller',
            'book__book_edition__book_work',
        )
        .prefetch_related(
            Prefetch(
                'book__images',
                queryset=images,
                to_attr='primary_images',
            ),
        )
    )


class SaleListingListCreateView(APIView):
    def get_permissions(self):
        permission = IsAuthenticated if self.request.method == 'POST' else AllowAny
        return [permission()]

    def get(self, request):
        queryset = listing_queryset(list_payload=True).filter(
            status='ACTIVE',
            book__status='AVAILABLE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        )
        params = request.query_params
        search = (params.get('search') or '').strip()
        if search:
            identifiers = BookIdentifier.objects.filter(
                book_edition_id=OuterRef('book__book_edition_id'),
                identifier_value__icontains=search,
            )
            queryset = queryset.annotate(
                _identifier_match=Exists(identifiers),
                _subject_match=Exists(
                    BookWorkSubject.objects.filter(
                        book_work_id=OuterRef('book__book_edition__book_work_id'),
                    ).filter(
                        Q(subject__name__icontains=search)
                        | Q(subject__code__icontains=search),
                    ),
                ),
            ).filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(book__book_edition__book_work__title__icontains=search)
                | Q(book__book_edition__book_work__description__icontains=search)
                | Q(book__book_edition__book_work__author_name__icontains=search)
                | Q(book__book_edition__edition_name__icontains=search)
                | Q(book__book_edition__publisher_name__icontains=search)
                | Q(book__book_edition__book_work__category__name__icontains=search)
                | Q(_identifier_match=True)
                | Q(_subject_match=True),
            )

        subject_id = self._integer_param(params, 'subject_id')
        if subject_id is not None:
            queryset = queryset.filter(Exists(
                BookWorkSubject.objects.filter(
                    book_work_id=OuterRef('book__book_edition__book_work_id'),
                    subject_id=subject_id,
                ),
            ))
        category_id = self._integer_param(params, 'category_id')
        if category_id is not None:
            queryset = queryset.filter(
                book__book_edition__book_work__category_id=category_id,
            )
        publication_year = self._integer_param(params, 'publication_year')
        if publication_year is not None:
            queryset = queryset.filter(
                book__book_edition__publication_year=publication_year,
            )
        language_id = self._integer_param(params, 'language_id')
        if language_id is not None:
            queryset = queryset.filter(book__book_edition__language_id=language_id)
        edition = (params.get('edition') or '').strip()
        if edition:
            queryset = queryset.filter(
                book__book_edition__edition_name__icontains=edition,
            )
        condition = params.get('condition_status')
        if condition:
            if condition not in {value for value, _ in Book.CONDITION_CHOICES}:
                raise serializers.ValidationError({
                    'condition_status': 'Tình trạng không hợp lệ.',
                })
            queryset = queryset.filter(
                book__condition_label__iexact=condition,
            )
        minimum = self._decimal_param(params, 'min_price')
        maximum = self._decimal_param(params, 'max_price')
        if minimum is not None:
            queryset = queryset.filter(price__gte=minimum)
        if maximum is not None:
            queryset = queryset.filter(price__lte=maximum)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError({
                'price': 'min_price không được lớn hơn max_price.',
            })
        sort_options = {
            'newest': ('-created_at', '-id'),
            'oldest': ('created_at', 'id'),
            'price_asc': ('price', 'id'),
            'price_desc': ('-price', '-id'),
        }
        sort = params.get('sort', 'newest')
        if sort not in sort_options:
            raise serializers.ValidationError({'sort': 'Giá trị sort không hợp lệ.'})
        queryset = queryset.order_by(*sort_options[sort])
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            sale_listing_payload(item, include_description=False) for item in page
        ])

    @staticmethod
    def _integer_param(params, name):
        value = params.get(name)
        if value in (None, ''):
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise serializers.ValidationError({name: f'{name} phải là số nguyên.'}) from exc
        if parsed < 1:
            raise serializers.ValidationError({name: f'{name} phải lớn hơn 0.'})
        return parsed

    @staticmethod
    def _decimal_param(params, name):
        value = params.get(name)
        if value in (None, ''):
            return None
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise serializers.ValidationError({name: f'{name} không hợp lệ.'}) from exc
        if not parsed.is_finite() or parsed < 0:
            raise serializers.ValidationError({name: f'{name} không được âm.'})
        return parsed

    @transaction.atomic
    def post(self, request):
        serializer = SaleListingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'book_id' not in data or 'price' not in data:
            raise serializers.ValidationError({
                'detail': 'book_id và price là bắt buộc.',
            })
        book = get_object_or_404(
            Book.objects.select_for_update(),
            pk=data['book_id'],
            owner=request.user,
            status='AVAILABLE',
        )
        if SaleListing.objects.filter(
            book=book,
            status__in=('PENDING', 'ACTIVE', 'RESERVED', 'SOLD'),
        ).exists():
            raise serializers.ValidationError({
                'book_id': 'Sách đã có listing chưa thể đăng bán lại.',
            })
        now = timezone.now()
        try:
            listing = SaleListing.objects.create(
                book=book,
                seller=request.user,
                title=data.get('title') or book.book_edition.book_work.title,
                description=data.get('description'),
                price=data['price'],
                status=data.get('status', 'PENDING'),
                published_at=None,
                created_at=now,
                updated_at=now,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError({
                'book_id': 'Sách đã có listing đang hoạt động.',
            }) from exc
        listing = listing_queryset().get(pk=listing.pk)
        return Response(
            sale_listing_payload(listing),
            status=status.HTTP_201_CREATED,
        )


class SaleListingDetailView(APIView):
    def get_permissions(self):
        permission = IsAuthenticated if self.request.method in ('PATCH', 'DELETE') else AllowAny
        return [permission()]

    def get(self, request, listing_id):
        queryset = listing_queryset()
        listing = get_object_or_404(queryset, pk=listing_id)
        if listing.status != 'ACTIVE' and (
            not request.user.is_authenticated
            or listing.seller_id != request.user.id
        ):
            raise PermissionDenied('Tin đăng không khả dụng.')
        return Response(sale_listing_payload(listing))

    @transaction.atomic
    def patch(self, request, listing_id):
        listing = get_object_or_404(
            SaleListing.objects.select_for_update().select_related('book'),
            pk=listing_id,
        )
        self._require_owner(request, listing)
        self._require_editable(listing)
        serializer = SaleListingInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'book_id' in data:
            raise serializers.ValidationError({'book_id': 'Không thể đổi sách của listing.'})
        if data.get('status') == 'ACTIVE':
            if listing.book.status != 'AVAILABLE':
                raise serializers.ValidationError({
                    'status': 'Chỉ có thể kích hoạt listing khi sách còn khả dụng.',
                })
            if SaleListing.objects.filter(
                book_id=listing.book_id,
                status__in=('PENDING', 'ACTIVE', 'RESERVED', 'SOLD'),
            ).exclude(pk=listing.pk).exists():
                raise serializers.ValidationError({
                    'status': 'Sách đã có listing chưa thể đăng bán lại.',
                })

        for field in ('title', 'description', 'price', 'status'):
            if field in data:
                setattr(listing, field, data[field])
        if listing.status == 'REJECTED' and any(
            field in data for field in ('title', 'description', 'price')
        ):
            listing.status = 'PENDING'
            listing.published_at = None
        now = timezone.now()
        listing.updated_at = now
        listing.save()
        listing = listing_queryset().get(pk=listing.pk)
        return Response(sale_listing_payload(listing))

    @transaction.atomic
    def delete(self, request, listing_id):
        listing = get_object_or_404(
            SaleListing.objects.select_for_update().select_related('book'),
            pk=listing_id,
        )
        self._require_owner(request, listing)
        self._require_editable(listing)
        if listing.status in ('RESERVED', 'SOLD'):
            raise serializers.ValidationError({
                'status': 'Tin đăng đang được giữ chỗ hoặc đã bán.',
            })
        listing.status = 'CLOSED'
        listing.updated_at = timezone.now()
        listing.save(update_fields=['status', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _require_owner(request, listing):
        if listing.seller_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền sửa tin đăng này.')

    @staticmethod
    def _require_editable(listing):
        if listing.status not in (
            'DRAFT', 'PENDING', 'ACTIVE', 'REJECTED', 'CLOSED', 'EXPIRED',
        ):
            raise serializers.ValidationError({
                'status': 'Tin đăng đang được giữ chỗ hoặc đã bán.',
            })
