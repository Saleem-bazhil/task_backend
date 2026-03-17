from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    # 1. These fields will show up as columns in the admin list view
    list_display = ('title', 'user', 'status', 'priority', 'due_date', 'created_at')
    
    # 2. This creates a filter sidebar on the right to easily sort tasks
    list_filter = ('status', 'priority', 'created_at')
    
    # 3. This adds a search bar at the top to find tasks by title or description
    search_fields = ('title', 'description', 'user__username')
    
    # 4. Makes the status directly editable from the list view without opening the task
    list_editable = ('status', 'priority')