from django.db import models

from users.models import User


class Notification(models.Model):
    user = models.ForeignKey(
        User, db_column='user_id', on_delete=models.DO_NOTHING,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    content = models.TextField()
    entity_type = models.CharField(max_length=50, null=True, blank=True)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    @property
    def type(self):
        return self.notification_type

    @property
    def reference_id(self):
        return self.entity_id

    class Meta:
        managed = False
        db_table = 'notifications'
