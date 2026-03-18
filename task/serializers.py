from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Task


class TaskUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role"]

    def get_role(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.role if profile else "employee"


class TaskSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="user",
        write_only=True,
        required=False,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "user",
            "user_id",
            "status",
            "priority",
            "due_date",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        is_admin = bool(
            request.user.is_authenticated
            and (
                request.user.is_staff
                or request.user.is_superuser
                or getattr(getattr(request.user, "userprofile", None), "role", "") == "admin"
            )
        )

        if request.method == "POST":
            if not is_admin:
                raise serializers.ValidationError("Only admins can assign tasks.")
            if "user" not in attrs:
                raise serializers.ValidationError({"user_id": "Assigned user is required."})

        if request.method in {"PUT", "PATCH"} and not is_admin and "user" in attrs:
            raise serializers.ValidationError({"user_id": "Employees cannot reassign tasks."})

        return attrs
