from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib.auth.models import User # <-- ADDED THIS IMPORT
from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'room', 'content', 'timestamp')
    list_filter = ('room', 'sender')
    search_fields = ('room', 'sender', 'content')
    ordering = ('-timestamp',)

    change_list_template = "message_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'live-chat/', 
                self.admin_site.admin_view(self.live_chat_view), 
                name='admin-live-chat'
            ),
        ]
        return custom_urls + urls

    # 2. Create the view that renders the HTML template
    def live_chat_view(self, request):
        # Fetch all users EXCEPT the currently logged-in admin
        real_users = User.objects.exclude(username=request.user.username).values_list('username', flat=True)

        context = dict(
           self.admin_site.each_context(request),
           title="Admin Live Chat",
           real_users=real_users, # <-- ADDED THIS TO PASS USERS TO HTML
        )
        
        # Kept your path exactly as is to prevent the TemplateDoesNotExist error!
        return TemplateResponse(request, "live_chat.html", context)
    