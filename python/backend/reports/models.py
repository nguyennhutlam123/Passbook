from django.db import models
from books.models import Book
from users.models import User


class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('reviewing', 'Reviewing'),
        ('resolved', 'Resolved'), ('rejected', 'Rejected'),
    ]

    id = models.AutoField(primary_key=True)
    reporter = models.ForeignKey(User, db_column='reporter_id', on_delete=models.CASCADE, related_name='reports')
    book = models.ForeignKey(
        Book, db_column='book_id', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reports',
    )
    reason = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'reports'
