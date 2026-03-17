from rest_framework.viewsets import ModelViewSet
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from .models import Task
from .serializers import TaskSerializer

class Taskview(ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        queryset = Task.objects.all()
        status_param = self.request.query_params.get('status', None)
        if status_param is not None:
            queryset = queryset.filter(status=status_param)
        return queryset

    # NEW: This hooks into the API update process
    def perform_update(self, serializer):
        # 1. Save the updated task to the database
        instance = serializer.save()

        # 2. Get the ID of the user making the request (fallback to 1 if testing without auth)
        user_id = self.request.user.id if self.request.user.is_authenticated else 1

        # 3. Manually write an entry into the Django Admin History
        LogEntry.objects.log_action(
            user_id=user_id,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=instance.pk,
            object_repr=str(instance),
            action_flag=CHANGE,
            change_message=f"Updated via React API (Status changed to: {instance.status})"
        )