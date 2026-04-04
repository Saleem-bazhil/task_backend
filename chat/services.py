from django.contrib.auth.models import User
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ChatRoom, Message
from .permissions import can_chat_with
from .serializers import MessageSerializer


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


def notify_room_message(message):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"chat_{message.room.room_id}",
        {
            "type": "chat.message",
            "message": MessageSerializer(message).data,
        },
    )


def get_visible_users_for(user, include_self=False):
    """
    Get all users that can be chatted with by the given user.
    
    Args:
        user: The requesting user
        include_self: If True, include the user themselves in the results
    
    Returns:
        List of User objects that the given user can chat with
    """
    # Start with all active users
    queryset = User.objects.filter(is_active=True).select_related("userprofile")
    
    # Exclude self unless explicitly requested
    if not include_self:
        queryset = queryset.exclude(id=user.id)
    
    # Convert to list and filter based on chat permissions
    # This ensures all users are visible (they can chat with anyone who's active)
    visible_users = [target for target in queryset if can_chat_with(user, target)]
    
    return visible_users
