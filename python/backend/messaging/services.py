from datetime import timedelta

from django.db import transaction
from django.db.models import Count, OuterRef, Subquery
from django.utils import timezone

from users.models import User

from .models import Conversation, ConversationMember


@transaction.atomic
def get_or_create_private_conversation(first_user_id, second_user_id):
    participant_ids = sorted({first_user_id, second_user_id})
    if len(participant_ids) != 2:
        raise ValueError('Private conversations require two different users.')

    list(
        User.objects.select_for_update()
        .filter(pk__in=participant_ids)
        .order_by('pk')
        .values_list('pk', flat=True)
    )
    candidate_ids = ConversationMember.objects.filter(
        user_id=participant_ids[0],
    ).values('conversation_id')
    participant_count = (
        ConversationMember.objects
        .filter(conversation_id=OuterRef('pk'))
        .values('conversation_id')
        .annotate(total=Count('user_id'))
        .values('total')
    )
    conversation = (
        Conversation.objects
        .filter(conversation_type='SALE', id__in=candidate_ids)
        .filter(members__user_id=participant_ids[1])
        .annotate(member_count=Subquery(participant_count))
        .filter(member_count=2)
        .order_by('-updated_at', '-id')
        .first()
    )
    if conversation is not None:
        return conversation, False

    now = timezone.now()
    conversation = Conversation.objects.create(
        conversation_type='SALE',
        created_at=now,
        updated_at=now,
    )
    ConversationMember.objects.bulk_create([
        ConversationMember(
            conversation=conversation,
            user_id=participant_ids[0],
            joined_at=now,
        ),
        ConversationMember(
            conversation=conversation,
            user_id=participant_ids[1],
            joined_at=now + timedelta(milliseconds=1),
        ),
    ])
    return conversation, True
