from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Book,
    BookIdentifier,
    BookImage,
    BookRequest,
    BorrowTerms,
    LendListing,
    BookWorkSubject,
    Favorite,
    LendListing,
    SaleListing,
)
from .pagination import BookPagination
from .serializers import (
    BookImageSerializer,
    BookListSerializer,
    BookSerializer,
    BookWriteSerializer,
    FavoriteSerializer,
)


def optimized_books_queryset(
    include_history=False,
    primary_images_only=False,
    list_payload=False,
    active_only=False,
):
    listings = SaleListing.objects.order_by('-created_at', '-id')
    if not include_history:
        now = timezone.now()
        listings = listings.filter(
            status__in=('ACTIVE',) if active_only else ('ACTIVE', 'RESERVED'),
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        )
    images = BookImage.objects.order_by('sort_order', 'id')
    if primary_images_only:
        images = images.filter(is_primary=True)
    if list_payload:
        listings = listings.only(
            'id',
            'book_id',
            'title',
            'price',
            'status',
            'created_at',
            'expires_at',
        )
        images = images.only('id', 'book_id', 'image_url', 'is_primary')
        subject_links = BookWorkSubject.objects.filter(is_primary=True).only(
            'book_work_id',
            'subject_id',
            'is_primary',
        ).select_related('subject').only(
            'book_work_id',
            'subject_id',
            'is_primary',
            'subject__id',
            'subject__name',
            'subject__code',
        )
        queryset = Book.objects.only(
            'id',
            'book_edition_id',
            'owner_id',
            'condition_label',
            'status',
            'owner__id',
            'owner__full_name',
            'owner__university_id',
            'owner__university__id',
            'owner__university__name',
            'book_edition__id',
            'book_edition__edition_name',
            'book_edition__publication_year',
            'book_edition__book_work_id',
            'book_edition__book_work__id',
            'book_edition__book_work__title',
            'book_edition__book_work__category_id',
            'book_edition__book_work__category__id',
            'book_edition__book_work__category__name',
        )
        selected_relations = (
            'owner',
            'owner__university',
            'book_edition__book_work__category',
        )
        intent_requests = BookRequest.objects.filter(
            book_work_id=OuterRef('book_edition__book_work_id'),
            status='OPEN',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        )
        queryset = queryset.annotate(
            buying_intent_count=Coalesce(
                Subquery(
                    intent_requests.filter(request_type='BUY')
                    .order_by()
                    .values('book_work_id')
                    .annotate(total=Count('user_id', distinct=True))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            selling_intent_count=Coalesce(
                Subquery(
                    intent_requests.filter(request_type='SELL_INTENT')
                    .order_by()
                    .values('book_work_id')
                    .annotate(total=Count('user_id', distinct=True))
                    .values('total')[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
        )
    else:
        subject_links = BookWorkSubject.objects.filter(
            is_primary=True,
        ).select_related('subject')
        queryset = Book.objects.all()
        selected_relations = (
            'owner',
            'owner__university',
            'book_edition__language',
            'book_edition__book_work',
            'book_edition__book_work__category',
        )
    prefetches = [
        Prefetch('images', queryset=images),
        Prefetch(
            'sale_listings',
            queryset=listings,
            to_attr='active_sale_listings',
        ),
        Prefetch(
            'book_edition__book_work__subject_links',
            queryset=subject_links,
            to_attr='primary_subject_links',
        ),
    ]
    if not list_payload:
        lend_listings = LendListing.objects.order_by('-created_at', '-id')
        if not include_history:
            lend_listings = lend_listings.filter(
                status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
            )
        lend_listings = lend_listings.prefetch_related(
            Prefetch(
                'borrow_terms',
                queryset=BorrowTerms.objects.only(
                    'id',
                    'lend_listing_id',
                    'max_days',
                    'late_fee_per_day',
                    'deposit_required',
                    'shipping_paid_by',
                    'return_method',
                    'notes',
                ),
                to_attr='listing_terms',
            ),
        )
        prefetches.append(
            Prefetch(
                'lend_listings',
                queryset=lend_listings,
                to_attr='active_lend_listings',
            ),
        )
    if not list_payload:
        prefetches.append(
            Prefetch(
                'book_edition__identifiers',
                queryset=BookIdentifier.objects.order_by('identifier_type', 'id'),
            ),
        )
    return queryset.select_related(*selected_relations).prefetch_related(*prefetches)


def _with_search(queryset, search):
    search = (search or '').strip()
    if not search:
        return queryset
    subject_match = BookWorkSubject.objects.filter(
        book_work_id=OuterRef('book_edition__book_work_id'),
    ).filter(
        Q(subject__name__icontains=search)
        | Q(subject__code__icontains=search)
    )
    sale_listing_match = SaleListing.objects.filter(
        book_id=OuterRef('pk'),
        status='ACTIVE',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
    ).filter(
        Q(title__icontains=search) | Q(description__icontains=search),
    )
    identifier_match = BookIdentifier.objects.filter(
        book_edition_id=OuterRef('book_edition_id'),
        identifier_value__icontains=search,
    )
    return (
        queryset
        .annotate(_subject_match=Exists(subject_match))
        .annotate(_sale_listing_match=Exists(sale_listing_match))
        .annotate(_identifier_match=Exists(identifier_match))
        .filter(
            Q(_sale_listing_match=True)
            | Q(book_edition__book_work__title__icontains=search)
            | Q(book_edition__book_work__description__icontains=search)
            | Q(book_edition__book_work__author_name__icontains=search)
            | Q(_subject_match=True)
            | Q(book_edition__edition_name__icontains=search)
            | Q(book_edition__publisher_name__icontains=search)
            | Q(book_edition__description__icontains=search)
            | Q(book_edition__book_work__category__name__icontains=search)
            | Q(owner__university__name__icontains=search)
            | Q(owner__faculty__name__icontains=search)
            | Q(owner__major__name__icontains=search)
            | Q(_identifier_match=True)
        )
    )


class BookListView(APIView):
    def get(self, request):
        queryset = optimized_books_queryset(
            primary_images_only=True,
            list_payload=True,
            active_only=True,
        ).filter(
            status='AVAILABLE',
        )
        now = timezone.now()
        active_listings = SaleListing.objects.filter(
            book_id=OuterRef('pk'),
            status='ACTIVE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        )
        queryset = queryset.filter(Exists(active_listings))
        query_params = request.query_params
        queryset = _with_search(queryset, query_params.get('search'))

        subject_id = self._filter_integer(query_params, 'subject_id')
        if subject_id is not None:
            queryset = queryset.filter(Exists(BookWorkSubject.objects.filter(
                book_work_id=OuterRef('book_edition__book_work_id'),
                subject_id=subject_id,
            )))
        category_id = self._filter_integer(query_params, 'category_id')
        if category_id is not None:
            queryset = queryset.filter(
                book_edition__book_work__category_id=category_id,
            )
        edition = query_params.get('edition')
        if edition:
            queryset = queryset.filter(
                book_edition__edition_name__icontains=edition.strip(),
            )
        publication_year = self._filter_integer(query_params, 'publication_year')
        if publication_year is not None:
            queryset = queryset.filter(
                book_edition__publication_year=publication_year,
            )
        language_id = self._filter_integer(query_params, 'language_id')
        if language_id is not None:
            queryset = queryset.filter(book_edition__language_id=language_id)
        university_id = self._filter_integer(query_params, 'university_id')
        if university_id is not None:
            queryset = queryset.filter(owner__university_id=university_id)
        faculty_id = self._filter_integer(query_params, 'faculty_id')
        if faculty_id is not None:
            queryset = queryset.filter(owner__faculty_id=faculty_id)
        major_id = self._filter_integer(query_params, 'major_id')
        if major_id is not None:
            queryset = queryset.filter(owner__major_id=major_id)
        author = (query_params.get('author') or '').strip()
        if author:
            queryset = queryset.filter(
                book_edition__book_work__author_name__icontains=author,
            )
        subject_code = (query_params.get('subject_code') or '').strip()
        if subject_code:
            queryset = queryset.filter(Exists(BookWorkSubject.objects.filter(
                book_work_id=OuterRef('book_edition__book_work_id'),
                subject__code__icontains=subject_code,
            )))
        subject = (query_params.get('subject') or '').strip()
        if subject:
            queryset = queryset.filter(Exists(BookWorkSubject.objects.filter(
                book_work_id=OuterRef('book_edition__book_work_id'),
            ).filter(
                Q(subject__name__icontains=subject)
                | Q(subject__code__icontains=subject),
            )))
        isbn = (query_params.get('isbn') or '').strip()
        if isbn:
            queryset = queryset.filter(Exists(BookIdentifier.objects.filter(
                book_edition_id=OuterRef('book_edition_id'),
                identifier_type__iexact='ISBN',
                identifier_value__icontains=isbn,
            )))
        if query_params.get('pickup_location_id') not in (None, ''):
            raise serializers.ValidationError({
                'pickup_location_id': 'Điểm nhận riêng không thuộc schema Lite; trường lọc này đã ngừng hỗ trợ.',
            })

        university = (query_params.get('university') or '').strip()
        if university:
            queryset = queryset.filter(
                owner__university__name__icontains=university,
            )
        faculty = (query_params.get('faculty') or '').strip()
        if faculty:
            queryset = queryset.filter(
                owner__faculty__name__icontains=faculty,
            )
        major = (query_params.get('major') or '').strip()
        if major:
            queryset = queryset.filter(
                owner__major__name__icontains=major,
            )

        condition = query_params.get('condition_status')
        if condition:
            valid_conditions = {value for value, _ in Book.CONDITION_CHOICES}
            if condition not in valid_conditions:
                raise serializers.ValidationError({
                    'condition_status': 'Tình trạng không hợp lệ.',
                })
            queryset = queryset.filter(condition_label=condition.upper())

        min_price = self._parse_price(query_params, 'min_price')
        max_price = self._parse_price(query_params, 'max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError({
                'price': 'min_price không được lớn hơn max_price.',
            })
        if min_price is not None:
            active_listings = active_listings.filter(price__gte=min_price)
        if max_price is not None:
            active_listings = active_listings.filter(price__lte=max_price)
        if min_price is not None or max_price is not None:
            queryset = queryset.filter(Exists(active_listings))

        sort_options = {
            'newest': ('-_catalog_created_at', '-id'),
            'oldest': ('_catalog_created_at', '-id'),
            'price_asc': ('_catalog_price', '-id'),
            'price_desc': ('-_catalog_price', '-id'),
        }
        sort = query_params.get('sort', 'newest')
        if sort not in sort_options:
            raise serializers.ValidationError({'sort': 'Giá trị sort không hợp lệ.'})
        sort_listings = SaleListing.objects.filter(
            book_id=OuterRef('pk'),
            status='ACTIVE',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        ).order_by('-created_at', '-id')
        if min_price is not None:
            sort_listings = sort_listings.filter(price__gte=min_price)
        if max_price is not None:
            sort_listings = sort_listings.filter(price__lte=max_price)
        queryset = queryset.annotate(
            _catalog_created_at=Subquery(sort_listings.values('created_at')[:1]),
            _catalog_price=Subquery(sort_listings.values('price')[:1]),
        ).order_by(*sort_options[sort])

        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            BookListSerializer(page, many=True).data,
        )

    @staticmethod
    def _filter_integer(query_params, parameter):
        value = query_params.get(parameter)
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise serializers.ValidationError({
                parameter: f'{parameter} phải là số nguyên.',
            }) from exc
        if parsed < 1:
            raise serializers.ValidationError({
                parameter: f'{parameter} phải lớn hơn 0.',
            })
        return parsed

    @staticmethod
    def _parse_price(query_params, parameter):
        value = query_params.get(parameter)
        if value is None:
            return None
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise serializers.ValidationError({
                parameter: f'{parameter} không hợp lệ.',
            }) from exc
        if parsed < 0:
            raise serializers.ValidationError({
                parameter: f'{parameter} không được âm.',
            })
        return parsed

    def post(self, request):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        serializer = BookWriteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        book = serializer.save()
        book = optimized_books_queryset().get(pk=book.pk)
        book.active_sale_listings = list(
            SaleListing.objects.filter(book_id=book.pk, status='PENDING')
            .order_by('-id')[:1],
        )
        if not book.active_sale_listings:
            book.active_lend_listings = list(
                LendListing.objects.filter(
                    book_id=book.pk,
                    status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
                ).order_by('-id')[:1],
            )
        return Response(BookSerializer(book).data, status=status.HTTP_201_CREATED)


class MyBooksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = optimized_books_queryset(
            include_history=True,
            primary_images_only=True,
        ).filter(
            owner_id=request.user.id,
        )
        query_params = request.query_params

        listing_status = query_params.get('status')
        if listing_status:
            status_map = {
                'available': 'AVAILABLE',
                'reserved': 'RESERVED',
                'sold': 'SOLD',
                'hidden': 'UNAVAILABLE',
                'deleted': 'UNAVAILABLE',
            }
            physical_status = status_map.get(listing_status.lower(), listing_status.upper())
            if physical_status not in {value for value, _ in Book.STATUS_CHOICES}:
                raise serializers.ValidationError({'status': 'Trạng thái không hợp lệ.'})
            queryset = queryset.filter(status=physical_status)

        queryset = _with_search(queryset, query_params.get('search'))
        sort_options = {
            'newest': ('-created_at', '-id'),
            'oldest': ('created_at', '-id'),
            'price_asc': ('_current_price', '-id'),
            'price_desc': ('-_current_price', '-id'),
        }
        sort = query_params.get('sort', 'newest')
        if sort not in sort_options:
            raise serializers.ValidationError({'sort': 'Giá trị sort không hợp lệ.'})
        queryset = queryset.annotate(
            _current_price=Subquery(
                SaleListing.objects.filter(book_id=OuterRef('pk'))
                .order_by('-created_at', '-id')
                .values('price')[:1],
            ),
        ).order_by(*sort_options[sort])

        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(BookSerializer(page, many=True).data)


class BookDetailView(APIView):
    def get(self, request, pk):
        book = get_object_or_404(
            optimized_books_queryset().filter(
                status='AVAILABLE',
                sale_listings__status='ACTIVE',
            ).filter(
                Q(sale_listings__expires_at__isnull=True)
                | Q(sale_listings__expires_at__gt=timezone.now()),
            ),
            pk=pk,
        )
        return Response(BookSerializer(book).data)

    def patch(self, request, pk):
        self._require_owner(request, pk)
        book = get_object_or_404(optimized_books_queryset(), pk=pk)
        serializer = BookWriteSerializer(
            book,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        book = serializer.save()
        book = optimized_books_queryset().get(pk=book.pk)
        return Response(BookSerializer(book).data)

    def delete(self, request, pk):
        self._require_owner(request, pk)
        book = get_object_or_404(Book, pk=pk)
        if book.lend_listings.filter(status__in=('RESERVED', 'ON_LOAN')).exists():
            raise serializers.ValidationError(
                {'status': 'Không thể gỡ sách đang được giữ hoặc cho mượn.'},
            )
        now = timezone.now()
        with transaction.atomic():
            book.sale_listings.filter(status__in=('ACTIVE', 'RESERVED')).update(
                status='CLOSED',
                updated_at=now,
            )
            book.lend_listings.filter(status='ACTIVE').update(
                status='CLOSED',
                updated_at=now,
            )
            book.status = 'UNAVAILABLE'
            book.updated_at = now
            book.save(update_fields=['status', 'updated_at'])
        return Response({'message': 'Đã xóa tin đăng.'})

    @staticmethod
    def _require_owner(request, pk):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        book = get_object_or_404(Book, pk=pk)
        if book.owner_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền chỉnh sửa tin đăng này.')


class BookSoldView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        if book.owner_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền cập nhật tin đăng này.')
        if not book.sale_listings.filter(status='ACTIVE').exists():
            raise serializers.ValidationError(
                {'listing_type': 'Chỉ tin BUY mới có thể đánh dấu đã bán.'},
            )
        now = timezone.now()
        with transaction.atomic():
            book.sale_listings.filter(status='ACTIVE').update(
                status='SOLD',
                updated_at=now,
            )
            book.status = 'SOLD'
            book.updated_at = now
            book.save(update_fields=['status', 'updated_at'])
        book = optimized_books_queryset().get(pk=book.pk)
        return Response(BookSerializer(book).data)


class BookImageListView(APIView):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id, status='AVAILABLE')
        images = BookImage.objects.filter(book=book).order_by('sort_order', 'id')
        return Response({
            'book_id': book.id,
            'images': BookImageSerializer(images, many=True).data,
        })

    def post(self, request, book_id):
        book = self._get_editable_book(request, book_id)
        serializer = BookImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        with transaction.atomic():
            current_images = BookImage.objects.select_for_update().filter(book=book)
            if current_images.count() >= 10:
                raise serializers.ValidationError({
                    'images': 'Mỗi sách được đăng tối đa 10 ảnh.',
                })
            image_url = serializer.validated_data['image_url']
            public_id = serializer.validated_data.get('cloudinary_public_id')
            if current_images.filter(image_url=image_url).exists() or (
                public_id
                and current_images.filter(cloudinary_public_id=public_id).exists()
            ):
                raise serializers.ValidationError({
                    'image_url': 'Ảnh này đã được thêm vào sách.',
                })
            is_primary = serializer.validated_data.get('is_primary', False)
            if not current_images.exists():
                is_primary = True
            if is_primary:
                BookImage.objects.filter(book=book, is_primary=True).update(
                    is_primary=False,
                )
            serializer.validated_data['is_primary'] = is_primary
            image = serializer.save(book=book, created_at=now)
        return Response(BookImageSerializer(image).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _get_editable_book(request, book_id):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        book = get_object_or_404(Book, pk=book_id)
        if book.status != 'AVAILABLE':
            raise serializers.ValidationError({
                'book': 'Chỉ có thể chỉnh sửa ảnh của sách đang hoạt động.',
            })
        if book.owner_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền chỉnh sửa ảnh của tin đăng này.')
        return book


class BookImageDetailView(APIView):
    def patch(self, request, book_id, image_id):
        book = BookImageListView._get_editable_book(request, book_id)
        image = get_object_or_404(BookImage, pk=image_id, book=book)
        serializer = BookImageSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get('is_primary') is True:
                BookImage.objects.filter(
                    book=book,
                    is_primary=True,
                ).exclude(pk=image.pk).update(is_primary=False)
            image = serializer.save()
        return Response(BookImageSerializer(image).data)

    def delete(self, request, book_id, image_id):
        book = BookImageListView._get_editable_book(request, book_id)
        image = get_object_or_404(BookImage, pk=image_id, book=book)
        with transaction.atomic():
            was_primary = image.is_primary
            image.delete()
            remaining = BookImage.objects.filter(book=book)
            if was_primary and remaining.exists() and not remaining.filter(
                is_primary=True,
            ).exists():
                promoted = remaining.order_by('sort_order', 'id').first()
                promoted.is_primary = True
                promoted.save(update_fields=['is_primary'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteCreateDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        is_favorite = Favorite.objects.filter(
            user=request.user,
            book_id=book_id,
        ).exists()
        return Response({'book_id': book_id, 'is_favorite': is_favorite})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id, status='AVAILABLE')
        listing = get_object_or_404(
            SaleListing.objects.filter(
                book=book,
                status='ACTIVE',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            ),
        )
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={
                'sale_listing': listing,
                'created_at': timezone.now(),
            },
        )
        return Response(
            {'book_id': book.id, 'is_favorite': True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, book_id):
        favorite = get_object_or_404(
            Favorite, user=request.user, book_id=book_id,
        )
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = (
            Favorite.objects
            .filter(user=request.user, book__status='AVAILABLE')
            .select_related(
                'book',
                'book__owner',
                'book__owner__university',
                'book__book_edition__book_work__category',
            )
            .prefetch_related(
                Prefetch(
                    'book__images',
                    queryset=BookImage.objects.filter(is_primary=True).order_by(
                        'sort_order', 'id',
                    ),
                ),
                Prefetch(
                    'book__sale_listings',
                    queryset=SaleListing.objects.filter(
                        status__in=('ACTIVE', 'RESERVED'),
                    ).order_by('-created_at', '-id'),
                    to_attr='active_sale_listings',
                ),
                Prefetch(
                    'book__book_edition__book_work__subject_links',
                    queryset=BookWorkSubject.objects.filter(is_primary=True)
                    .select_related('subject'),
                    to_attr='primary_subject_links',
                ),
            )
            .order_by('-created_at', '-id')
        )
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            FavoriteSerializer(page, many=True).data,
        )
