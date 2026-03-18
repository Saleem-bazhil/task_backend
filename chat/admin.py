from django.contrib import admin

from .models import ChatRoom, Message


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("room_id", "user_one", "user_two", "updated_at")
    search_fields = ("room_id", "user_one__username", "user_two__username")
    ordering = ("-updated_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("room", "sender", "receiver", "timestamp")
    search_fields = ("room__room_id", "sender__username", "receiver__username", "content")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)
