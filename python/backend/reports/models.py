from django.db import models

from books.models import Book, LendListing, SaleListing
from users.models import User


class Report(models.Model):
    reporter = models.ForeignKey(
        User, db_column='reporter_id', on_delete=models.DO_NOTHING,
        related_name='reports',
    )
    reported_user = models.ForeignKey(
        User, db_column='reported_user_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='reports_about',
    )
    book = models.ForeignKey(
        Book, db_column='book_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='reports',
    )
    sale_listing = models.ForeignKey(
        SaleListing, db_column='sale_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='reports',
    )
    lend_listing = models.ForeignKey(
        LendListing, db_column='lend_listing_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='reports',
    )
    message = models.ForeignKey(
        'messaging.Message', db_column='message_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='reports',
    )
    reason = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='OPEN')
    handled_by = models.ForeignKey(
        User, db_column='handled_by', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='handled_reports',
    )
    resolution_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'reports'
