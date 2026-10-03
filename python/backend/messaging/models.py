from django.db import models

from users.models import User


class Conversation(models.Model):
    conversation_type = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'conversations'


class ConversationMember(models.Model):
    conversation = models.ForeignKey(
        Conversation, db_column='conversation_id', primary_key=True,
        on_delete=models.DO_NOTHING, related_name='members',
    )
    user = models.ForeignKey(
        User, db_column='user_id', on_delete=models.DO_NOTHING,
        related_name='conversation_memberships',
    )
    joined_at = models.DateTimeField()
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'conversation_members'
        unique_together = [('conversation', 'user')]


class Message(models.Model):
    MESSAGE_TYPES = [('TEXT', 'Text'), ('IMAGE', 'Image'), ('SYSTEM', 'System')]

    conversation = models.ForeignKey(
        Conversation, db_column='conversation_id', on_delete=models.DO_NOTHING,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User, db_column='sender_id', on_delete=models.DO_NOTHING,
        related_name='messages',
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField()
    attachment_url = models.URLField(max_length=2048, null=True, blank=True)
    sent_at = models.DateTimeField()
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'messages'
