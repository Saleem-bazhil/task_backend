import os

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Q

from .models import Task, Notification, TaskComment, TaskAttachment, TaskHistory
from .serializers import (
    TaskSerializer, 
    TaskUserSerializer, 
    NotificationSerializer, 
    TaskCommentSerializer, 
    TaskAttachmentSerializer,
    TaskHistorySerializer
)
from .notification_service import (
    notify_task_assigned,
    notify_task_updated,
    notify_comment_added,
    notify_task_completed
)


def is_admin_user(user):
    return bool(
        user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or getattr(getattr(user, "userprofile", None), "role", "") == "admin"
        )
    )


def get_task_queryset_for(user):
    """
    Get tasks visible to the user in collaborative system.
    Users can see:
    - Tasks they created
    - Tasks assigned to them
    - Tasks they're participating in (comments/attachments)
    Admins see all tasks.
    """
    from django.db.models import Q
    
    if is_admin_user(user):
        # Admins see all tasks
        queryset = Task.objects.select_related(
            "user",
            "user__userprofile",
            "assigned_by",
            "assigned_by__userprofile",
        ).prefetch_related("assigned_to").all()
    else:
        # Regular users see tasks they're involved with
        queryset = Task.objects.select_related(
            "user",
            "user__userprofile",
            "assigned_by",
            "assigned_by__userprofile",
        ).prefetch_related("assigned_to").filter(
            Q(user=user) |  # Created by them
            Q(assigned_to__id=user.id)  # Assigned to them
        ).distinct()
    
    return queryset


class TaskDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_task_queryset_for(request.user)
        now = timezone.now()

        total = queryset.count()
        pending = queryset.filter(status="pending").count()
        in_progress = queryset.filter(status="in_progress").count()
        completed = queryset.filter(status="completed").count()
        overdue = queryset.filter(due_date__lt=now).exclude(status="completed").count()
        due_soon = queryset.filter(due_date__gte=now, due_date__lte=now + timedelta(days=7)).exclude(status="completed").count()

        recent_tasks = TaskSerializer(queryset.order_by("-updated_at")[:6], many=True, context={'request': request}).data

        activities = []
        for task in queryset.order_by("-updated_at")[:6]:
            status_text = task.status
            if status_text == "completed":
                action_str = "completed"
                detail = f'"{task.title}" was marked completed.'
            elif status_text == "in_progress":
                action_str = "in_progress"
                detail = f'"{task.title}" is currently in progress.'
            else:
                action_str = "assigned"
                detail = f'"{task.title}" is pending review.'

            activities.append(
                {
                    "id": task.id,
                    "action": action_str,
                    "title": task.title,
                    "detail": detail,
                    "timestamp": task.updated_at,
                    "assigned_to": {
                        "id": task.user.id if task.user else None,
                        "username": task.user.username if task.user else "Unassigned",
                    },
                }
            )

        activity_data = []
        for i in range(6, -1, -1):
            day = now.date() - timedelta(days=i)
            created = queryset.filter(created_at__date=day).count()
            completed_on = queryset.filter(status="completed", updated_at__date=day).count()
            activity_data.append({
                "date": day.strftime("%a"),
                "created": created,
                "completed": completed_on
            })

        return Response(
            {
                "viewer_role": "admin" if is_admin_user(request.user) else "employee",
                "stats": {
                    "total": total,
                    "pending": pending,
                    "in_progress": in_progress,
                    "completed": completed,
                    "overdue": overdue,
                    "due_soon": due_soon,
                },
                "recent_tasks": recent_tasks,
                "activities": activities,
                "activity_data": activity_data,
            }
        )


class TaskAssignableUserListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskUserSerializer

    def get_queryset(self):
        # Allow anyone to see users to assign tasks to? The user said "everyone can receive task"
        # and "next show the user name who will we assign". So we always list all users.
        return User.objects.filter(is_active=True).select_related("userprofile").order_by("username")


class Taskview(ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_task_queryset_for(self.request.user)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        task = serializer.save(user=self.request.user)

        if task.assigned_to.exists() and not task.assigned_by:
            task.assigned_by = self.request.user
            task.save()

        TaskHistory.objects.create(
            task=task,
            user=self.request.user,
            action='created',
            description=f'Task "{task.title}" was created.'
        )

        for assigned_user in task.assigned_to.all():
            notify_task_assigned(task, assigned_user, self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        old_priority = instance.priority
        old_title = instance.title
        old_due_date = str(instance.due_date) if instance.due_date else ''
        old_assigned_ids = set(instance.assigned_to.values_list('id', flat=True))

        # In collaborative system, anyone can update tasks they're involved with
        # Still validate that non-admins can't modify tasks they're not involved with
        if not is_admin_user(self.request.user):
            is_creator = instance.user == self.request.user
            is_assigned = self.request.user in instance.assigned_to.all()
            if not (is_creator or is_assigned):
                raise PermissionDenied("You can only update tasks you're involved with.")

        updated_instance = serializer.save()
        self.log_admin_change(updated_instance)

        actor = self.request.user

        # Record history entries for each changed field
        if old_status != updated_instance.status:
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='status_changed',
                field_name='status', old_value=old_status, new_value=updated_instance.status,
                description=f'Status changed from "{old_status}" to "{updated_instance.status}".'
            )
            
            # Notify on status change
            if updated_instance.status == 'completed':
                notify_task_completed(updated_instance, actor)
            else:
                notify_task_updated(updated_instance, actor, 'status')

        if old_priority != updated_instance.priority:
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='priority_changed',
                field_name='priority', old_value=old_priority, new_value=updated_instance.priority,
                description=f'Priority changed from "{old_priority}" to "{updated_instance.priority}".'
            )
            notify_task_updated(updated_instance, actor, 'priority')

        if old_title != updated_instance.title:
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='updated',
                field_name='title', old_value=old_title, new_value=updated_instance.title,
                description=f'Title changed from "{old_title}" to "{updated_instance.title}".'
            )
            notify_task_updated(updated_instance, actor, 'title')

        new_due = str(updated_instance.due_date) if updated_instance.due_date else ''
        if old_due_date != new_due:
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='due_date_changed',
                field_name='due_date', old_value=old_due_date, new_value=new_due,
                description=f'Due date updated.'
            )
            notify_task_updated(updated_instance, actor, 'due_date')

        # Track changes to assigned_to field
        new_assigned_ids = set(updated_instance.assigned_to.values_list('id', flat=True))
        newly_assigned_ids = new_assigned_ids - old_assigned_ids
        unassigned_ids = old_assigned_ids - new_assigned_ids

        # Notify newly assigned users and update assignment ownership when the assignee list changes.
        if newly_assigned_ids and not updated_instance.assigned_by:
            updated_instance.assigned_by = actor
            updated_instance.save()

        for user_id in newly_assigned_ids:
            assigned_user = User.objects.get(id=user_id)
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='assigned',
                field_name='assigned_to',
                old_value='',
                new_value=assigned_user.username,
                description=f'Assigned to {assigned_user.username}.'
            )
            notify_task_assigned(updated_instance, assigned_user, actor)

        # Notify unassigned users (for tracking purposes)
        for user_id in unassigned_ids:
            unassigned_user = User.objects.get(id=user_id)
            TaskHistory.objects.create(
                task=updated_instance, user=actor, action='unassigned',
                field_name='assigned_to',
                old_value=unassigned_user.username,
                new_value='',
                description=f'Unassigned from {unassigned_user.username}.'
            )

    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response(
                {"detail": "Only admins can delete tasks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def log_admin_change(self, instance):
        LogEntry.objects.log_action(
            user_id=self.request.user.id,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=instance.pk,
            object_repr=str(instance),
            action_flag=CHANGE,
            change_message=f"Updated via API (Status: {instance.status})",
        )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """GET /tasks/{id}/history/ — returns the full change history for a task."""
        task = self.get_object()
        entries = TaskHistory.objects.filter(task=task).select_related('user', 'user__userprofile')
        serializer = TaskHistorySerializer(entries, many=True)
        return Response(serializer.data)


class TaskCreatedByMeView(generics.ListAPIView):
    """Tasks created by the current user"""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Task.objects.select_related("user", "user__userprofile", "assigned_by").prefetch_related("assigned_to").filter(
            user=self.request.user
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset.order_by("-created_at")


class TaskAssignedToMeView(generics.ListAPIView):
    """Tasks assigned to the current user"""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Task.objects.select_related("user", "user__userprofile", "assigned_by").prefetch_related("assigned_to").filter(
            assigned_to__id=self.request.user.id
        ).exclude(user=self.request.user)  # Exclude tasks created by the user to avoid duplication
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset.order_by("-created_at")


class TaskCommentViewSet(ModelViewSet):
    serializer_class = TaskCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        In collaborative system, users can see comments on tasks they're involved with.
        """
        if is_admin_user(self.request.user):
            return TaskComment.objects.all()
        
        # Users see comments only on tasks they're involved with
        visible_tasks = get_task_queryset_for(self.request.user)
        return TaskComment.objects.filter(task__in=visible_tasks)

    def perform_create(self, serializer):
        task_id = self.request.data.get("task")
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            raise PermissionDenied("Task not found.")
            
        # In collaborative system, anyone involved with the task can comment
        if not is_admin_user(self.request.user):
            is_creator = task.user == self.request.user
            is_assigned = self.request.user in task.assigned_to.all()
            if not (is_creator or is_assigned):
                raise PermissionDenied("You can only comment on tasks you're involved with.")
        
        comment = serializer.save(user=self.request.user)
        
        # Notify all task participants about the new comment
        notify_comment_added(comment, self.request.user)


class TaskAttachmentViewSet(ModelViewSet):
    serializer_class = TaskAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 10 MB max upload size
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.txt', '.csv', '.rtf', '.odt', '.ods',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
        # Archives
        '.zip', '.rar', '.7z', '.tar', '.gz',
    }

    def get_queryset(self):
        """
        In collaborative system, users can see attachments on tasks they're involved with.
        """
        if is_admin_user(self.request.user):
            return TaskAttachment.objects.all()

        visible_tasks = get_task_queryset_for(self.request.user)
        return TaskAttachment.objects.filter(task__in=visible_tasks)

    def perform_create(self, serializer):
        task_id = self.request.data.get("task")
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            raise PermissionDenied("Task not found.")

        # In collaborative system, anyone involved with the task can upload files
        if not is_admin_user(self.request.user):
            is_creator = task.user == self.request.user
            is_assigned = self.request.user in task.assigned_to.all()
            if not (is_creator or is_assigned):
                raise PermissionDenied("You can only attach files to tasks you're involved with.")

        file_obj = self.request.FILES.get('file')
        if not file_obj:
            raise PermissionDenied("No file uploaded.")

        # Validate file size
        if file_obj.size > self.MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"File too large. Maximum size is {self.MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
            )

        # Validate file extension
        _, ext = os.path.splitext(file_obj.name)
        if ext.lower() not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"
            )

        serializer.save(user=self.request.user, filename=file_obj.name)


class NotificationViewSet(ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """GET /notifications/unread_count/ — Get count of unread notifications."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """POST /notifications/mark_all_read/ — Mark all notifications as read."""
        from django.utils import timezone
        now = timezone.now()
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=now
        )
        return Response({"status": "ok"})

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """POST /notifications/{id}/mark_as_read/ — Mark single notification as read."""
        from django.utils import timezone
        notification = self.get_object()
        if notification.user != request.user:
            return Response(
                {"detail": "You cannot mark other users' notifications."},
                status=status.HTTP_403_FORBIDDEN
            )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        return Response(NotificationSerializer(notification).data)
