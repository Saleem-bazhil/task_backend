from django.contrib.auth.models import User
from rest_framework import serializers

from .models import ChatRoom, Message
from user.models import UserProfile


class ChatUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role"]

    def get_role(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.role if profile else UserProfile.EMPLOYEE


class MessageSerializer(serializers.ModelSerializer):
    sender = ChatUserSerializer(read_only=True)
    receiver = ChatUserSerializer(read_only=True)
    room_id = serializers.CharField(source="room.room_id", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "room_id",
            "sender",
            "receiver",
            "content",
            "timestamp",
        ]


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ["id", "room_id", "participants", "created_at", "updated_at"]

    def get_participants(self, obj):
        return ChatUserSerializer([obj.user_one, obj.user_two], many=True).data


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ["id", "room_id", "other_user", "last_message", "updated_at"]

    def get_other_user(self, obj):
        request = self.context["request"]
        return ChatUserSerializer(obj.get_other_user(request.user)).data

    def get_last_message(self, obj):
        last_message = obj.messages.select_related("sender", "receiver").order_by("-timestamp", "-id").first()
        return MessageSerializer(last_message).data if last_message else None


class RoomRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
