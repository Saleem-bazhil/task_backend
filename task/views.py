from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from rest_framework.decorators import action

from .models import Task, Notification
from .serializers import TaskSerializer, TaskUserSerializer, NotificationSerializer


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
    queryset = Task.objects.select_related("user", "user__userprofile").all()
    if not is_admin_user(user):
        queryset = queryset.filter(user=user)
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

        recent_tasks = TaskSerializer(queryset.order_by("-updated_at")[:6], many=True).data

        activities = []
        for task in queryset.order_by("-updated_at")[:6]:
            if task.status == "completed":
                action = "completed"
                detail = f'"{task.title}" was marked completed.'
            elif task.status == "in_progress":
                action = "in_progress"
                detail = f'"{task.title}" is currently in progress.'
            else:
                action = "assigned"
                detail = f'"{task.title}" is pending review.'

            activities.append(
                {
                    "id": task.id,
                    "action": action,
                    "title": task.title,
                    "detail": detail,
                    "timestamp": task.updated_at,
                    "assigned_to": {
                        "id": task.user.id,
                        "username": task.user.username,
                    },
                }
            )

        activity_data = []
        for i in range(6, -1, -1):
            day = now.date() - timedelta(days=i)
            # Use __date lookup for accuracy since we want the exact day
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
        queryset = User.objects.filter(is_active=True).select_related("userprofile").order_by("username")
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(id=self.request.user.id)


class Taskview(ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_task_queryset_for(self.request.user)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def create(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response(
                {"detail": "Only admins can assign tasks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        task = serializer.save()
        if hasattr(task, 'user') and getattr(task, 'user', None):
            Notification.objects.create(
                user=task.user,
                title="System",
                action=f"assigned you a new task: '{task.title[:30]}'",
                project="Task App",
                status="success"
            )

    def perform_update(self, serializer):
        instance = self.get_object()
        incoming_user = serializer.validated_data.get("user")
        old_user = getattr(instance, 'user', None)

        if not is_admin_user(self.request.user):
            if incoming_user and incoming_user != instance.user:
                raise PermissionDenied("Employees cannot reassign tasks.")

        updated_instance = serializer.save()
        self.log_admin_change(updated_instance)

        if old_user != updated_instance.user and getattr(updated_instance, 'user', None):
            Notification.objects.create(
                user=updated_instance.user,
                title=self.request.user.first_name or self.request.user.username,
                action=f"assigned you the task: '{updated_instance.title[:30]}'",
                project="Task App",
                status="success"
            )
        elif self.request.user != updated_instance.user and getattr(updated_instance, 'user', None):
            Notification.objects.create(
                user=updated_instance.user,
                title=self.request.user.first_name or self.request.user.username,
                action=f"updated your task: '{updated_instance.title[:30]}'",
                project="Task App",
                status="success"
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
            change_message=f"Updated via API (Status changed to: {instance.status})",
        )

class NotificationViewSet(ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')[:30]

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"status": "ok"})
