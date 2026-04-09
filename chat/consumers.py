import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatRoom
from .serializers import MessageSerializer
from .services import create_message, notify_room_message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.room = await self.get_room()
        if not self.room:
            await self.close(code=4004)
            return

        self.group_name = f"chat_{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid payload.")
            return

        content = (payload.get("message") or "").strip()
        if not content:
            await self.send_error("Message content is required.")
            return

        await self.persist_message(content)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def send_error(self, detail):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))

    @database_sync_to_async
    def get_room(self):
        room = (
            ChatRoom.objects.select_related(
                "user_one",
                "user_two",
                "user_one__userprofile",
                "user_two__userprofile",
            )
            .filter(room_id=self.room_id)
            .first()
        )
        if not room or not room.includes_user(self.user):
            return None
        return room

    @database_sync_to_async
    def persist_message(self, content):
        message = create_message(self.room, self.user, content)
        notify_room_message(message)
        return MessageSerializer(message).data


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time task notifications.
    Connects user to their personal notification channel.
    """

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Create a unique group for this user's notifications
        self.notification_group_name = f"notification_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "notification_group_name"):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )

    # Receive notification from group and send to WebSocket
    async def notification_message(self, event):
        """
        Handle notification event from group and send to WebSocket.
        Called when a notification is broadcast to this group.
        """
        notification = event["notification"]
        
        await self.send(text_data=json.dumps({
            "type": "notification",
            "data": notification
        }))

    async def send_error(self, detail):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))
