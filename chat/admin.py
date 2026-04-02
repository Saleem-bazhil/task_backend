from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Prefetch, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.crypto import get_random_string
from django.utils.formats import date_format
from django.utils.text import Truncator
from unfold.admin import ModelAdmin

from .models import ChatRoom, Message
from .permissions import can_chat_with, is_admin_user
from .services import create_message, get_or_create_room_for_users

User = get_user_model()


@admin.register(ChatRoom)
class ChatRoomAdmin(ModelAdmin):
    list_display = ("room_id", "participants", "message_count", "updated_at")
    search_fields = ("room_id", "user_one__username", "user_two__username")
    ordering = ("-updated_at",)
    list_select_related = ("user_one", "user_two")

    def get_model_perms(self, request):
        # Hide raw chat room model from the admin index/sidebar.
        return {}

    @admin.display(description="Participants")
    def participants(self, obj):
        return f"{obj.user_one.username} and {obj.user_two.username}"

    @admin.display(ordering="message_total", description="Messages")
    def message_count(self, obj):
        return obj.message_total

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(message_total=Count("messages"))


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    change_list_template = "message_change_list.html"
    selected_employee_session_key = "admin_chat_selected_employee"
    list_display = ("room", "sender", "receiver", "preview", "timestamp")
    search_fields = ("room__room_id", "sender__username", "receiver__username", "content")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)
    list_select_related = ("room", "sender", "receiver")

    def get_model_perms(self, request):
        # Keep the custom live chat view accessible by URL, but hide the raw message model entry.
        return {}

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "live-chat/feed/",
                self.admin_site.admin_view(self.live_chat_feed_view),
                name="chat_message_live_chat_feed",
            ),
            path(
                "live-chat/",
                self.admin_site.admin_view(self.live_chat_view),
                name="chat_message_live_chat",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Message")
    def preview(self, obj):
        return Truncator(obj.content).chars(60)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        # Allow access to the changelist endpoint for redirect to live chat, but deny direct object views.
        return obj is None

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:chat_message_live_chat"))

    def live_chat_view(self, request):
        employee_queryset = (
            User.objects.filter(is_active=True)
            .exclude(id=request.user.id)
            .select_related("userprofile")
            .order_by("username")
        )
        employees = [user for user in employee_queryset if can_chat_with(request.user, user)]
        employees_by_id = {employee.id: employee for employee in employees}

        selected_employee = None
        room = None
        selected_user_id = (
            request.POST.get("employee")
            or request.GET.get("employee")
            or request.session.get(self.selected_employee_session_key)
        )

        if selected_user_id:
            try:
                selected_employee = employees_by_id[int(selected_user_id)]
                request.session[self.selected_employee_session_key] = selected_employee.id
                request.session.modified = True
            except (KeyError, ValueError):
                request.session.pop(self.selected_employee_session_key, None)
                request.session.modified = True
                messages.error(request, "That employee is not available for chat.")
        else:
            request.session.pop(self.selected_employee_session_key, None)
            request.session.modified = True

        if selected_employee:
            room = get_or_create_room_for_users(request.user, selected_employee)

        if request.method == "POST":
            content = (request.POST.get("message") or "").strip()
            form_token = request.POST.get("form_token") or ""
            if not selected_employee:
                messages.error(request, "Select an employee before sending a message.")
            elif not content:
                messages.error(request, "Enter a message before sending.")
            elif not self._consume_form_token(request, form_token):
                messages.info(request, "That message form was already used. Refresh prevented a duplicate send.")
                return HttpResponseRedirect(f"{request.path}?employee={selected_employee.id}")
            else:
                create_message(room, request.user, content)
                messages.success(request, f"Message sent to {selected_employee.username}.")
                return HttpResponseRedirect(f"{request.path}?employee={selected_employee.id}")

        chat_messages = self._get_chat_messages(room)
        conversation_cards = self._get_conversation_cards(request.user, selected_employee)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Admin chat with employees",
            "employees": employees,
            "selected_employee": selected_employee,
            "chat_messages": chat_messages,
            "conversation_cards": conversation_cards,
            "form_token": self._issue_form_token(request),
            "selected_employee_id": selected_employee.id if selected_employee else "",
            "selected_room_id": room.room_id if room else "",
            "live_feed_url": reverse("admin:chat_message_live_chat_feed"),
            "conversation_count": len(conversation_cards),
            "message_count": chat_messages.count() if room else 0,
        }
        return TemplateResponse(request, "live_chat.html", context)

    def live_chat_feed_view(self, request):
        employee_id = request.GET.get("employee")
        selected_employee = self._get_selected_employee(request, employee_id)
        room = get_or_create_room_for_users(request.user, selected_employee) if selected_employee else None
        chat_messages = list(self._get_chat_messages(room)) if room else []
        conversation_cards = self._get_conversation_cards(request.user, selected_employee)

        return JsonResponse(
            {
                "selected_employee": {
                    "id": selected_employee.id,
                    "username": selected_employee.username,
                    "full_name": selected_employee.get_full_name().strip(),
                }
                if selected_employee
                else None,
                "room_id": room.room_id if room else "",
                "message_count": len(chat_messages),
                "messages": [
                    {
                        "id": message.id,
                        "content": message.content,
                        "timestamp": message.timestamp.isoformat(),
                        "timestamp_label": date_format(message.timestamp, "M j, Y, P"),
                        "sender_id": message.sender_id,
                        "sender_name": message.sender.username,
                        "is_me": message.sender_id == request.user.id,
                    }
                    for message in chat_messages
                ],
                "conversation_cards": [
                    {
                        "employee_id": card["employee"].id,
                        "username": card["employee"].username,
                        "is_selected": card["is_selected"],
                        "preview": card["last_message"].content if card["last_message"] else "",
                        "has_messages": bool(card["last_message"]),
                    }
                    for card in conversation_cards
                ],
            }
        )

    def _get_selected_employee(self, request, employee_id):
        if not employee_id:
            return None

        employee_queryset = (
            User.objects.filter(is_active=True)
            .exclude(id=request.user.id)
            .select_related("userprofile")
            .order_by("username")
        )
        employees = [user for user in employee_queryset if can_chat_with(request.user, user)]
        employees_by_id = {employee.id: employee for employee in employees}
        try:
            return employees_by_id[int(employee_id)]
        except (KeyError, ValueError):
            return None

    def _get_chat_messages(self, room):
        if not room:
            return Message.objects.none()
        return room.messages.select_related("sender", "receiver").order_by("timestamp", "id")

    def _get_conversation_cards(self, admin_user, selected_employee):
        recent_rooms = (
            ChatRoom.objects.filter(Q(user_one=admin_user) | Q(user_two=admin_user))
            .select_related("user_one", "user_two")
            .annotate(last_message_at=Max("messages__timestamp"))
            .prefetch_related(
                Prefetch(
                    "messages",
                    queryset=Message.objects.select_related("sender", "receiver").order_by(
                        "-timestamp", "-id"
                    ),
                    to_attr="prefetched_messages",
                )
            )
            .order_by("-last_message_at", "-updated_at")
        )

        conversation_cards = []
        for recent_room in recent_rooms:
            other_user = recent_room.get_other_user(admin_user)
            if is_admin_user(other_user):
                continue
            conversation_cards.append(
                {
                    "employee": other_user,
                    "last_message": recent_room.prefetched_messages[0]
                    if recent_room.prefetched_messages
                    else None,
                    "is_selected": bool(selected_employee and selected_employee.id == other_user.id),
                }
            )
        return conversation_cards

    def _issue_form_token(self, request):
        tokens = request.session.get("admin_chat_form_tokens", [])
        token = get_random_string(24)
        tokens.append(token)
        request.session["admin_chat_form_tokens"] = tokens[-10:]
        request.session.modified = True
        return token

    def _consume_form_token(self, request, token):
        if not token:
            return False

        tokens = request.session.get("admin_chat_form_tokens", [])
        if token not in tokens:
            return False

        tokens.remove(token)
        request.session["admin_chat_form_tokens"] = tokens
        request.session.modified = True
        return True
