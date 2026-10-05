from django.contrib import admin

from config.composite_admin import CompositeKeyAdmin

from .models import Conversation, ConversationMember, Message

admin.site.register((Conversation, Message))


@admin.register(ConversationMember)
class ConversationMemberAdmin(CompositeKeyAdmin):
    composite_key_fields = ('conversation', 'user')
    list_display = (
        'composite_key_link',
        'conversation_id',
        'user_id',
        'joined_at',
        'last_read_at',
        'composite_delete_link',
    )
    ordering = ('conversation_id', 'user_id')
