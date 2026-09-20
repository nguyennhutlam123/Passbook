from rest_framework import serializers
from urllib.parse import urlparse

from .models import Book, BookImage, Category, Favorite, Location
from users.models import Subject


class BookSellerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    university_id = serializers.IntegerField(allow_null=True)


class BookSubjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField(allow_null=True)


class BookCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')


class BookLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'name')


class BookImageSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    sort_order = serializers.IntegerField(min_value=0, required=False, default=0)
    is_primary = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = BookImage
        fields = ('id', 'image_url', 'is_primary', 'sort_order')
        read_only_fields = ('id',)

    def validate_image_url(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('image_url không được để trống.')
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise serializers.ValidationError('image_url phải là URL HTTP/HTTPS hợp lệ.')
        if parsed.scheme != 'https':
            raise serializers.ValidationError('image_url phải sử dụng HTTPS.')
        return value


class FavoriteBookSerializer(serializers.ModelSerializer):
    seller = BookSellerSerializer(read_only=True)
    images = BookImageSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = ('id', 'title', 'price', 'condition_status', 'status', 'seller', 'images')


class FavoriteSerializer(serializers.ModelSerializer):
    book = FavoriteBookSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ('id', 'book', 'created_at')


class BookSerializer(serializers.ModelSerializer):
    condition_label = serializers.CharField(source='get_condition_status_display', read_only=True)
    seller = BookSellerSerializer(read_only=True)
    subject = BookSubjectSerializer(read_only=True, allow_null=True)
    category = BookCategorySerializer(read_only=True, allow_null=True)
    pickup_location = BookLocationSerializer(read_only=True, allow_null=True)
    images = BookImageSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = (
            'id', 'title', 'description', 'price', 'condition_status', 'condition_label',
            'edition', 'publication_year', 'status', 'seller', 'subject', 'category',
            'pickup_location', 'images', 'created_at', 'updated_at',
        )


class BookWriteSerializer(serializers.ModelSerializer):
    subject_id = serializers.PrimaryKeyRelatedField(
        source='subject', queryset=Subject.objects.all(), required=False, allow_null=True,
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source='category', queryset=Category.objects.all(), required=False, allow_null=True,
    )
    pickup_location_id = serializers.PrimaryKeyRelatedField(
        source='pickup_location', queryset=Location.objects.all(), required=False, allow_null=True,
    )
    title = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    condition_status = serializers.ChoiceField(choices=Book.CONDITION_CHOICES)
    publication_year = serializers.IntegerField(required=False, allow_null=True, min_value=1900, max_value=2100)

    class Meta:
        model = Book
        fields = (
            'subject_id', 'category_id', 'pickup_location_id', 'title', 'description',
            'price', 'condition_status', 'edition', 'publication_year', 'pickup_note',
        )

    def validate_title(self, value):
        return value.strip()
