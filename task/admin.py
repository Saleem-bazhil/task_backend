from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Task

@admin.register(Task)
class TaskAdmin(ModelAdmin):
    # 1. These fields will show up as columns in the admin list view
    list_display = ('title', 'user', 'status', 'priority', 'due_date', 'created_at')
    
    # 2. This creates a filter sidebar on the right to easily sort tasks
    list_filter = ('status', 'priority', 'created_at')
    
    # 3. This adds a search bar at the top to find tasks by title or description
    search_fields = ('title', 'description', 'user__username')
    
    # 4. Makes the status directly editable from the list view without opening the task
    list_editable = ('status', 'priority')
    
    # 5. Admin interface display configuration
    filter_horizontal = ('assigned_to',)  # Better UX for ManyToMany selection in admin
    readonly_fields = ('assigned_by', 'created_at', 'updated_at', 'user')
    
    fieldsets = (
        ('Task Information', {
            'fields': ('title', 'description', 'user', 'status', 'priority', 'due_date')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_by'),
            'description': 'Select users to assign this task to. assigned_by is automatically set to the admin user making the change.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to properly handle ManyToMany assigned_to field.
        - Only set assigned_by to request.user (the admin making the change)
        - Do NOT overwrite assigned_to with request.user
        - ManyToMany fields are handled via the admin form's save_m2m() method
        """
        # If assigning users, set assigned_by to current admin user
        if form.cleaned_data.get('assigned_to'):
            obj.assigned_by = request.user
        
        # Save the task instance (without ManyToMany)
        obj.save()
        
        # Django admin automatically calls save_m2m() after save_model(),
        # which properly saves the ManyToMany assigned_to relationship
