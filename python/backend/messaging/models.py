from django.db import models
from books.models import Book
from users.models import User


class Conversation(models.Model):
    id = models.AutoField(primary_key=True)
    book = models.ForeignKey(Book, db_column='book_id', on_delete=models.CASCADE, related_name='conversations')
    buyer = models.ForeignKey(User, db_column='buyer_id', on_delete=models.CASCADE, related_name='buyer_conversations')
    seller = models.ForeignKey(User, db_column='seller_id', on_delete=models.CASCADE, related_name='seller_conversations')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'conversations'
        unique_together = [('book', 'buyer', 'seller')]


class Message(models.Model):
    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation, db_column='conversation_id', on_delete=models.CASCADE, related_name='messages',
    )
    sender = models.ForeignKey(User, db_column='sender_id', on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'messages'
