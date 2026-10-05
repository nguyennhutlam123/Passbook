from django.db import models
from users.models import User, Subject


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'categories'


class Location(models.Model):
    id = models.AutoField(primary_key=True)
    university = models.ForeignKey(
        'users.University', db_column='university_id', on_delete=models.CASCADE,
        related_name='locations',
    )
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'locations'


class Book(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'), ('like_new', 'Like new'), ('good', 'Good'), ('used', 'Used'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'), ('reserved', 'Reserved'), ('sold', 'Sold'),
        ('hidden', 'Hidden'), ('deleted', 'Deleted'),
    ]

    id = models.AutoField(primary_key=True)
    seller = models.ForeignKey(
        User, db_column='seller_id', on_delete=models.CASCADE, related_name='books',
    )
    subject = models.ForeignKey(
        Subject, db_column='subject_id', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='books',
    )
    category = models.ForeignKey(
        Category, db_column='category_id', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='books',
    )
    pickup_location = models.ForeignKey(
        Location, db_column='pickup_location_id', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='books',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    condition_status = models.CharField(max_length=8, choices=CONDITION_CHOICES, default='used')
    edition = models.CharField(max_length=100, null=True, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default='available')
    pickup_note = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'books'


class BookImage(models.Model):
    id = models.AutoField(primary_key=True)
    book = models.ForeignKey(Book, db_column='book_id', on_delete=models.CASCADE, related_name='images')
    image_url = models.CharField(max_length=500)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'book_images'


class Favorite(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.CASCADE, related_name='favorites')
    book = models.ForeignKey(Book, db_column='book_id', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'favorites'
        unique_together = [('user', 'book')]
