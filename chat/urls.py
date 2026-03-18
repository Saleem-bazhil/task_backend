from django.urls import path

from .views import ConversationListView, MessageListView, RoomView, UserListView

urlpatterns = [
    path("chat/users/", UserListView.as_view(), name="chat-users"),
    path("chat/conversations/", ConversationListView.as_view(), name="chat-conversations"),
    path("chat/rooms/", RoomView.as_view(), name="chat-room-create"),
    path("chat/rooms/<slug:room_id>/", RoomView.as_view(), name="chat-room-detail"),
    path("chat/rooms/<slug:room_id>/messages/", MessageListView.as_view(), name="chat-room-messages"),
]
