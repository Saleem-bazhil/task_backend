from django.contrib.auth.models import User
from django.db import transaction

from .models import ChatRoom, Message
from .permissions import can_chat_with


def get_or_create_room_for_users(user_a, user_b):
    if not can_chat_with(user_a, user_b):
        raise ValueError("These users are not allowed to chat.")

    low_user, high_user = sorted([user_a, user_b], key=lambda item: item.id)
    room, _ = ChatRoom.objects.get_or_create(user_one=low_user, user_two=high_user)
    return room


@transaction.atomic
def create_message(room, sender, content):
    if not room.includes_user(sender):
        raise ValueError("Sender does not belong to this room.")

    receiver = room.get_other_user(sender)
    return Message.objects.create(
        room=room,
        sender=sender,
        receiver=receiver,
        content=content.strip(),
    )


def get_visible_users_for(user):
    queryset = User.objects.filter(is_active=True).exclude(id=user.id).select_related("userprofile")
    return [target for target in queryset if can_chat_with(user, target)]
