from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ("user", "role")
    search_fields = ("user__username", "user__email")
