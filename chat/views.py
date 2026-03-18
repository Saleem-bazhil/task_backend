from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ChatRoom, Message
from .permissions import can_chat_with
from .serializers import (
    ChatRoomSerializer,
    ChatUserSerializer,
    ConversationSerializer,
    MessageSerializer,
    RoomRequestSerializer,
)
from .services import get_or_create_room_for_users, get_visible_users_for


class UserListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatUserSerializer

    def get_queryset(self):
        return get_visible_users_for(self.request.user)


class ConversationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            ChatRoom.objects.filter(Q(user_one=user) | Q(user_two=user))
            .select_related(
                "user_one",
                "user_one__userprofile",
                "user_two",
                "user_two__userprofile",
            )
            .prefetch_related("messages__sender__userprofile", "messages__receiver__userprofile")
        )


class MessageListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        room = ChatRoom.objects.filter(room_id=self.kwargs["room_id"]).first()
        if not room or not room.includes_user(self.request.user):
            return Message.objects.none()
        return (
            room.messages.select_related(
                "sender",
                "sender__userprofile",
                "receiver",
                "receiver__userprofile",
                "room",
            )
        )


class RoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoomRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user = generics.get_object_or_404(User.objects.select_related("userprofile"), id=serializer.validated_data["user_id"])
        if not can_chat_with(request.user, target_user):
            return Response(
                {"detail": "You are not allowed to chat with this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        room = get_or_create_room_for_users(request.user, target_user)
        return Response(ChatRoomSerializer(room).data, status=status.HTTP_200_OK)

    def get(self, request, room_id):
        room = generics.get_object_or_404(
            ChatRoom.objects.select_related(
                "user_one",
                "user_one__userprofile",
                "user_two",
                "user_two__userprofile",
            ),
            room_id=room_id,
        )
        if not room.includes_user(request.user):
            return Response({"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ChatRoomSerializer(room).data, status=status.HTTP_200_OK)
