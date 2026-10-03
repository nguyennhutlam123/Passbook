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
    SaleListing,
)


class BookSellerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source='full_name')
    university_id = serializers.IntegerField(allow_null=True)


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


class BookListImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookImage
        fields = ('id', 'image_url', 'is_primary')


class BookSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    price = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    condition_status = serializers.CharField(read_only=True)
    condition_label = serializers.SerializerMethodField()
    edition = serializers.CharField(read_only=True, allow_null=True)
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()
    seller = BookSellerSerializer(read_only=True)
    subject = BookSubjectSerializer(read_only=True, allow_null=True)
    category = BookCategorySerializer(read_only=True, allow_null=True)
    pickup_location = serializers.SerializerMethodField()
    images = BookListImageSerializer(many=True, read_only=True)
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
        return {
            'AVAILABLE': 'available',
            'RESERVED': 'reserved',
            'ON_LOAN': 'available',
            'SOLD': 'sold',
            'UNAVAILABLE': 'hidden',
        }.get(book.status, book.status.lower())

    @staticmethod
    def get_pickup_location(_book):
        return None


class BookListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    condition_status = serializers.CharField(read_only=True)
    condition_label = serializers.SerializerMethodField()
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    primary_image = serializers.SerializerMethodField()
    subject = BookSubjectSerializer(read_only=True, allow_null=True)
    category = BookCategorySerializer(read_only=True, allow_null=True)
    seller = BookSellerSerializer(read_only=True)

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
    price = serializers.DecimalField(max_digits=19, decimal_places=4, min_value=0)
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
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        from django.utils import timezone

        now = timezone.now()
        subject = validated_data.pop('subject', None)
        category = validated_data.pop('category', None)
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
        return book

    def update(self, book, validated_data):
        from django.utils import timezone

        work = book.book_edition.book_work
        listing = book.sale_listings.filter(status__in=('ACTIVE', 'RESERVED')).first()
        if listing is None:
            raise serializers.ValidationError({'status': 'Tin đăng không còn hoạt động.'})
        now = timezone.now()
        with transaction.atomic():
            if 'title' in validated_data:
                listing.title = validated_data['title']
                work.title = validated_data['title']
            if 'description' in validated_data:
                listing.description = validated_data['description']
                work.description = validated_data['description']
            if 'price' in validated_data:
                listing.price = validated_data['price']
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
