from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import Task
from .serializers import TaskSerializer


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
            }
        )


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
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        incoming_user = serializer.validated_data.get("user")

        if not is_admin_user(self.request.user):
            if incoming_user and incoming_user != instance.user:
                raise PermissionDenied("Employees cannot reassign tasks.")

        updated_instance = serializer.save()
        self.log_admin_change(updated_instance)

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
