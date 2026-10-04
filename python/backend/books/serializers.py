from decimal import Decimal
from urllib.parse import urlparse

from django.db import transaction
from rest_framework import serializers

from users.models import Subject
from .models import (
    Book,
    BookImage,
    BookWork,
    BookWorkSubject,
    BookEdition,
    Category,
    Favorite,
    BorrowTerms,
    LendListing,
    SaleListing,
)


class BookSellerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source='full_name')
    university_id = serializers.IntegerField(allow_null=True)
    university = serializers.SerializerMethodField()

    @staticmethod
    def get_university(user):
        if user.university_id is None or user.university is None:
            return None
        return {'id': user.university_id, 'name': user.university.name}


class BookSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ('id', 'name', 'code')


class BookCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')


class BookLocationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class BookImageSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(max_length=2048, allow_blank=False, trim_whitespace=True)
    sort_order = serializers.IntegerField(min_value=0, required=False, default=0)
    is_primary = serializers.BooleanField(required=False, default=False)
    cloudinary_public_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = BookImage
        fields = ('id', 'image_url', 'cloudinary_public_id', 'is_primary', 'sort_order')
        read_only_fields = ('id',)

    def validate_image_url(self, value):
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.netloc:
            raise serializers.ValidationError('image_url phải là URL HTTPS hợp lệ.')
        return value


class BookImageManifestSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, required=False)
    image_url = serializers.CharField(max_length=2048, allow_blank=False, trim_whitespace=True)
    cloudinary_public_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    is_primary = serializers.BooleanField(required=False, default=False)
    sort_order = serializers.IntegerField(min_value=0, required=False)

    def validate_image_url(self, value):
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.netloc:
            raise serializers.ValidationError('image_url phải là URL HTTPS hợp lệ.')
        return value


class BookListImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookImage
        fields = ('id', 'image_url', 'is_primary')


class BookSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    price = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    rental_fee = serializers.SerializerMethodField()
    deposit_amount = serializers.SerializerMethodField()
    borrow_terms = serializers.SerializerMethodField()
    listing_type = serializers.SerializerMethodField()
    listing_id = serializers.SerializerMethodField()
    condition_status = serializers.CharField(read_only=True)
    condition_label = serializers.SerializerMethodField()
    edition = serializers.CharField(
        source='book_edition.edition_name',
        read_only=True,
        allow_null=True,
    )
    edition_number = serializers.IntegerField(
        source='book_edition.edition_number',
        read_only=True,
        allow_null=True,
    )
    book_work_id = serializers.IntegerField(
        source='book_edition.book_work_id',
        read_only=True,
    )
    author = serializers.CharField(
        source='book_edition.book_work.author_name',
        read_only=True,
        allow_null=True,
    )
    publisher = serializers.CharField(
        source='book_edition.publisher_name',
        read_only=True,
        allow_null=True,
    )
    condition_description = serializers.CharField(read_only=True, allow_null=True)
    isbn = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()
    seller = BookSellerSerializer(read_only=True)
    subject = BookSubjectSerializer(read_only=True, allow_null=True)
    category = BookCategorySerializer(read_only=True, allow_null=True)
    pickup_location = serializers.SerializerMethodField()
    images = BookImageSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    @staticmethod
    def get_condition_label(book):
        labels = dict(Book.CONDITION_CHOICES)
        return labels.get(book.condition_status, book.condition_label)

    @staticmethod
    def get_status(book):
        listing = book._active_sale_listing()
        if listing is not None and listing.status == 'RESERVED':
            return 'reserved'
        if listing is not None and listing.status == 'SOLD':
            return 'sold'
        lend_listing = book._active_lend_listing()
        if lend_listing is not None and lend_listing.status == 'RESERVED':
            return 'reserved'
        if lend_listing is not None and lend_listing.status == 'ON_LOAN':
            return 'on_loan'
        return {
            'AVAILABLE': 'available',
            'RESERVED': 'reserved',
            'ON_LOAN': 'on_loan',
            'SOLD': 'sold',
            'UNAVAILABLE': 'hidden',
        }.get(book.status, book.status.lower())

    @staticmethod
    def get_pickup_location(_book):
        return None

    @staticmethod
    def get_listing_type(book):
        if book._active_sale_listing() is not None:
            return 'BUY'
        return 'BORROW' if book._active_lend_listing() is not None else 'BUY'

    @staticmethod
    def get_listing_id(book):
        listing = book._active_sale_listing() or book._active_lend_listing()
        return listing.id if listing is not None else None

    @staticmethod
    def get_rental_fee(book):
        listing = book._active_lend_listing()
        return listing.rental_fee if listing is not None else None

    @staticmethod
    def get_deposit_amount(book):
        listing = book._active_lend_listing()
        return listing.deposit_amount if listing is not None else None

    @staticmethod
    def get_borrow_terms(book):
        listing = book._active_lend_listing()
        if listing is None:
            return None
        terms = getattr(listing, 'listing_terms', None)
        if terms is None:
            return None
        return {
            'max_days': terms.max_days,
            'late_fee_per_day': terms.late_fee_per_day,
            'deposit_required': terms.deposit_required,
            'shipping_paid_by': terms.shipping_paid_by,
            'return_method': terms.return_method,
            'notes': terms.notes,
        }

    @staticmethod
    def get_isbn(book):
        identifiers = getattr(book.book_edition, 'identifiers', None)
        if identifiers is None:
            return None
        for identifier in identifiers.all():
            if 'ISBN' in identifier.identifier_type.upper():
                return identifier.identifier_value
        return None

    @staticmethod
    def get_language(book):
        language = book.book_edition.language
        if language is None:
            return None
        return {'id': language.id, 'name': language.name, 'code': language.code}


class BookListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    condition_status = serializers.CharField(read_only=True)
    condition_label = serializers.SerializerMethodField()
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    edition = serializers.CharField(
        source='book_edition.edition_name',
        read_only=True,
        allow_null=True,
    )
    primary_image = serializers.SerializerMethodField()
    subject = BookSubjectSerializer(read_only=True, allow_null=True)
    category = BookCategorySerializer(read_only=True, allow_null=True)
    seller = BookSellerSerializer(read_only=True)
    buying_intent_count = serializers.IntegerField(read_only=True, default=0)
    selling_intent_count = serializers.IntegerField(read_only=True, default=0)

    @staticmethod
    def get_condition_label(book):
        labels = dict(Book.CONDITION_CHOICES)
        return labels.get(book.condition_status, book.condition_label)

    @staticmethod
    def get_primary_image(book):
        images = getattr(book, '_prefetched_objects_cache', {}).get('images')
        if images is None:
            return None
        image = next(iter(images), None)
        if image is None:
            return None
        return {'id': image.id, 'image_url': image.image_url}


class BookWriteSerializer(serializers.Serializer):
    subject_id = serializers.PrimaryKeyRelatedField(
        source='subject', queryset=Subject.objects.filter(status='ACTIVE'),
        required=False, allow_null=True,
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source='category', queryset=Category.objects.filter(status='ACTIVE'),
        required=False, allow_null=True,
    )
    title = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    listing_type = serializers.ChoiceField(
        choices=('BUY', 'BORROW'),
        required=False,
        default='BUY',
    )
    price = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=Decimal('0.0001'),
        required=False,
    )
    rental_fee = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
    )
    deposit_amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    max_days = serializers.IntegerField(min_value=1, required=False)
    late_fee_per_day = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    deposit_required = serializers.BooleanField(required=False, default=False)
    shipping_paid_by = serializers.CharField(max_length=20, required=False)
    return_method = serializers.CharField(max_length=30, required=False)
    terms_notes = serializers.CharField(required=False, allow_blank=True)
    images = BookImageManifestSerializer(
        many=True,
        required=False,
        max_length=10,
        allow_empty=True,
    )
    condition_status = serializers.ChoiceField(choices=Book.CONDITION_CHOICES)
    edition = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    publication_year = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=9999)
    pickup_location_id = serializers.JSONField(required=False, write_only=True)
    pickup_note = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        if self.initial_data.get('pickup_location_id') not in (None, ''):
            raise serializers.ValidationError({
                'pickup_location_id': 'Điểm nhận riêng không thuộc schema Lite; trường này đã ngừng hỗ trợ.',
            })
        if self.initial_data.get('pickup_note'):
            raise serializers.ValidationError({
                'pickup_note': 'Ghi chú điểm nhận riêng không thuộc schema Lite; trường này đã ngừng hỗ trợ.',
            })
        if 'images' in attrs:
            images = attrs['images']
            urls = [image['image_url'] for image in images]
            public_ids = [
                image.get('cloudinary_public_id')
                for image in images
                if image.get('cloudinary_public_id')
            ]
            image_ids = [
                image['id'] for image in images if 'id' in image
            ]
            if len(urls) != len(set(urls)):
                raise serializers.ValidationError({
                    'images': 'Không thể thêm cùng một ảnh nhiều lần.',
                })
            if len(public_ids) != len(set(public_ids)):
                raise serializers.ValidationError({
                    'images': 'Cloudinary ảnh bị trùng.',
                })
            if len(image_ids) != len(set(image_ids)):
                raise serializers.ValidationError({
                    'images': 'Ảnh hiện tại bị lặp trong danh sách.',
                })
            if sum(bool(image.get('is_primary')) for image in images) > 1:
                raise serializers.ValidationError({
                    'images': 'Chỉ được chọn một ảnh chính.',
                })
            for index, image in enumerate(images):
                image.setdefault('sort_order', index)
        listing_type = attrs.get(
            'listing_type',
            'BORROW' if self.instance and self.instance._active_lend_listing() else 'BUY',
        )
        if listing_type == 'BUY':
            if not self.partial and 'price' not in attrs:
                raise serializers.ValidationError({'price': 'Giá bán là bắt buộc.'})
            if 'rental_fee' in attrs:
                raise serializers.ValidationError({
                    'rental_fee': 'Phí mượn chỉ áp dụng cho tin cho mượn.',
                })
        else:
            required = ('rental_fee', 'max_days', 'shipping_paid_by', 'return_method')
            missing = [field for field in required if field not in attrs]
            if not self.partial and missing:
                raise serializers.ValidationError({
                    field: 'Trường này bắt buộc với tin cho mượn.'
                    for field in missing
                })
            if 'price' in attrs:
                raise serializers.ValidationError({
                    'price': 'Tin cho mượn không sử dụng giá bán; hãy dùng rental_fee.',
                })
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        from django.utils import timezone

        now = timezone.now()
        subject = validated_data.pop('subject', None)
        category = validated_data.pop('category', None)
        listing_type = validated_data.pop('listing_type', 'BUY')
        rental_fee = validated_data.pop('rental_fee', None)
        deposit_amount = validated_data.pop('deposit_amount', None)
        max_days = validated_data.pop('max_days', None)
        late_fee_per_day = validated_data.pop('late_fee_per_day', None)
        deposit_required = validated_data.pop('deposit_required', False)
        shipping_paid_by = validated_data.pop('shipping_paid_by', None)
        return_method = validated_data.pop('return_method', None)
        terms_notes = validated_data.pop('terms_notes', None)
        images = validated_data.pop('images', None)
        title = validated_data['title']
        description = validated_data.get('description')
        condition = validated_data['condition_status']
        with transaction.atomic():
            work = BookWork.objects.create(
                title=title,
                description=description,
                category=category,
                created_by=self.context['request'].user,
                status='ACTIVE',
                created_at=now,
                updated_at=now,
            )
            if subject is not None:
                BookWorkSubject.objects.create(
                    book_work=work,
                    subject=subject,
                    is_primary=True,
                    created_at=now,
                )
            edition = BookEdition.objects.create(
                book_work=work,
                edition_name=validated_data.get('edition') or None,
                publication_year=validated_data.get('publication_year'),
                created_at=now,
                updated_at=now,
            )
            book = Book.objects.create(
                book_edition=edition,
                owner=self.context['request'].user,
                condition_label=condition.upper(),
                status='AVAILABLE',
                created_at=now,
                updated_at=now,
            )
            if images:
                if not any(image['is_primary'] for image in images):
                    images[0]['is_primary'] = True
                BookImage.objects.bulk_create([
                    BookImage(
                        book=book,
                        image_url=image['image_url'],
                        cloudinary_public_id=image.get('cloudinary_public_id'),
                        is_primary=image['is_primary'],
                        sort_order=image['sort_order'],
                        created_at=now,
                    )
                    for image in images
                ])
            if listing_type == 'BUY':
                listing = SaleListing.objects.create(
                    book=book,
                    seller=self.context['request'].user,
                    title=title,
                    description=description,
                    price=validated_data['price'],
                    status='PENDING',
                    published_at=None,
                    created_at=now,
                    updated_at=now,
                )
                book.active_sale_listings = [listing]
            else:
                listing = LendListing.objects.create(
                    book=book,
                    lender=self.context['request'].user,
                    title=title,
                    description=description,
                    rental_fee=rental_fee,
                    deposit_amount=deposit_amount,
                    status='ACTIVE',
                    published_at=now,
                    created_at=now,
                    updated_at=now,
                )
                terms = BorrowTerms.objects.create(
                    lend_listing=listing,
                    max_days=max_days,
                    late_fee_per_day=late_fee_per_day,
                    deposit_required=deposit_required,
                    shipping_paid_by=shipping_paid_by,
                    return_method=return_method,
                    notes=terms_notes,
                    created_at=now,
                    updated_at=now,
                )
                listing.listing_terms = terms
                book.active_lend_listings = [listing]
        return book

    def update(self, book, validated_data):
        from django.utils import timezone

        work = book.book_edition.book_work
        sale_listing = book.sale_listings.filter(
            status__in=('PENDING', 'ACTIVE', 'RESERVED'),
        ).first()
        lend_listing = book.lend_listings.filter(
            status__in=('ACTIVE', 'RESERVED', 'ON_LOAN'),
        ).first()
        listing_type = 'BUY' if sale_listing is not None else 'BORROW'
        if sale_listing is None and lend_listing is None:
            raise serializers.ValidationError({'status': 'Tin đăng không còn hoạt động.'})
        if (
            (sale_listing is not None and sale_listing.status == 'RESERVED')
            or (lend_listing is not None and lend_listing.status != 'ACTIVE')
        ):
            raise serializers.ValidationError({
                'status': 'Không thể sửa tin đang được giữ hoặc cho mượn.',
            })
        if validated_data.get('listing_type', listing_type) != listing_type:
            raise serializers.ValidationError({
                'listing_type': 'Không thể đổi hình thức của tin đăng hiện có.',
            })
        listing = sale_listing or lend_listing
        now = timezone.now()
        with transaction.atomic():
            image_manifest = validated_data.pop('images', None)
            if image_manifest is not None:
                current_images = {
                    image.id: image
                    for image in BookImage.objects.select_for_update().filter(book=book)
                }
                requested_ids = {
                    image['id'] for image in image_manifest if 'id' in image
                }
                if not requested_ids.issubset(current_images):
                    raise serializers.ValidationError({
                        'images': 'Danh sách chứa ảnh không thuộc sách này.',
                    })
                BookImage.objects.filter(book=book).update(is_primary=False)
                BookImage.objects.filter(book=book).exclude(
                    pk__in=requested_ids,
                ).delete()
                if image_manifest and not any(
                    image['is_primary'] for image in image_manifest
                ):
                    image_manifest[0]['is_primary'] = True
                for image_data in image_manifest:
                    image_id = image_data.pop('id', None)
                    image = current_images.get(image_id) if image_id else BookImage(
                        book=book,
                        created_at=now,
                    )
                    image.image_url = image_data['image_url']
                    image.cloudinary_public_id = image_data.get('cloudinary_public_id')
                    image.is_primary = image_data['is_primary']
                    image.sort_order = image_data['sort_order']
                    image.save()
            if 'title' in validated_data:
                listing.title = validated_data['title']
                work.title = validated_data['title']
            if 'description' in validated_data:
                listing.description = validated_data['description']
                work.description = validated_data['description']
            if 'price' in validated_data:
                if lend_listing is not None:
                    raise serializers.ValidationError({
                        'price': 'Tin cho mượn không sử dụng giá bán.',
                    })
                listing.price = validated_data['price']
            if 'rental_fee' in validated_data:
                if lend_listing is None:
                    raise serializers.ValidationError({
                        'rental_fee': 'Phí mượn chỉ áp dụng cho tin cho mượn.',
                    })
                listing.rental_fee = validated_data['rental_fee']
            if 'deposit_amount' in validated_data and lend_listing is not None:
                listing.deposit_amount = validated_data['deposit_amount']
            if 'condition_status' in validated_data:
                book.condition_label = validated_data['condition_status'].upper()
            if 'edition' in validated_data:
                book.book_edition.edition_name = validated_data['edition'] or None
            if 'publication_year' in validated_data:
                book.book_edition.publication_year = validated_data['publication_year']
            if 'category' in validated_data:
                work.category = validated_data['category']
            if 'subject' in validated_data:
                BookWorkSubject.objects.filter(
                    book_work=work, is_primary=True,
                ).update(is_primary=False)
                if validated_data['subject'] is not None:
                    BookWorkSubject.objects.create(
                        book_work=work,
                        subject=validated_data['subject'],
                        is_primary=True,
                        created_at=now,
                    )
            listing.updated_at = now
            work.updated_at = now
            book.updated_at = now
            book.book_edition.updated_at = now
            listing.save()
            if lend_listing is not None:
                terms = getattr(lend_listing, 'listing_terms', None)
                if terms is None:
                    terms = BorrowTerms.objects.filter(
                        lend_listing=lend_listing,
                    ).first()
                if terms is None:
                    raise serializers.ValidationError({
                        'borrow_terms': 'Tin cho mượn thiếu điều kiện mượn trong schema.',
                    })
                for field in (
                    'max_days',
                    'late_fee_per_day',
                    'deposit_required',
                    'shipping_paid_by',
                    'return_method',
                ):
                    if field in validated_data:
                        setattr(terms, field, validated_data[field])
                if 'terms_notes' in validated_data:
                    terms.notes = validated_data['terms_notes']
                terms.updated_at = now
                terms.save()
            work.save()
            book.save()
            book.book_edition.save()
        return book


class FavoriteBookSerializer(BookListSerializer):
    pass


class FavoriteSerializer(serializers.ModelSerializer):
    book = FavoriteBookSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ('id', 'book', 'created_at')
