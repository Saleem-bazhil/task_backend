from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Task, Notification, TaskComment, TaskAttachment, TaskHistory


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or getattr(getattr(user, "userprofile", None), "role", "") == "admin"
        )
    )


class TaskUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role", "full_name"]

    def get_role(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.role if profile else "employee"
        
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class TaskCommentSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "task", "user", "content", "created_at"]
        read_only_fields = ["user", "created_at"]


class TaskAttachmentSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskAttachment
        fields = ["id", "task", "user", "file", "filename", "file_url", "created_at"]
        read_only_fields = ["user", "created_at", "filename"]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            # S3 storage returns absolute URLs already; just return them
            url = obj.file.url
            if url.startswith("http"):
                return url
            # Local storage: build absolute URL from request
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class TaskSerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="user",
        write_only=True,
        required=False,
        allow_null=True
    )
    
    # Support multiple assignees for collaborative task management
    assigned_to = TaskUserSerializer(many=True, read_only=True)
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="assigned_to",
        many=True,
        write_only=True,
        required=False
    )
    
    # Track who assigned the task
    assigned_by = TaskUserSerializer(read_only=True)
    assigned_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="assigned_by",
        write_only=True,
        required=False,
        allow_null=True
    )
    
    comments = TaskCommentSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "user",
            "user_id",
            "assigned_to",
            "assigned_to_ids",
            "assigned_by",
            "assigned_by_id",
            "status",
            "priority",
            "due_date",
            "created_at",
            "updated_at",
            "comments",
            "attachments",
            "comments_count",
            "attachments_count",
            "last_message_preview",
        ]

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_attachments_count(self, obj):
        return obj.attachments.count()

    def get_last_message_preview(self, obj):
        last_comment = obj.comments.order_by("-created_at").first()
        if last_comment:
            return {
                "user": last_comment.user.username,
                "content": last_comment.content[:100],
                "created_at": last_comment.created_at
            }
        return None

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            return attrs

        current_user = request.user
        assigned_by = attrs.get("assigned_by")
        assigned_to = attrs.get("assigned_to")

        # Allow all assignment flows between admin and employee roles.
        # This includes:
        #   Admin → Employee
        #   Employee → Admin
        #   Admin → Admin
        #   Employee → Employee
        # The validation focuses on assignment ownership rather than restricting role pairs.
        if assigned_by and assigned_by != current_user and not is_admin_user(current_user):
            raise ValidationError({
                "assigned_by_id": "You may only set yourself as the assigning user unless you are an admin."
            })

        if assigned_to is not None and len(assigned_to) == 0 and assigned_by:
            raise ValidationError({
                "assigned_to_ids": "Cannot assign a task without at least one assignee."
            })

        # Automatically record assignment ownership from the current user when assigning a task
        if assigned_to is not None and not assigned_by:
            attrs["assigned_by"] = current_user

        return attrs

    def create(self, validated_data):
        """Override create to properly handle ManyToMany fields."""
        assigned_to_users = validated_data.pop("assigned_to", [])
        task = Task.objects.create(**validated_data)
        
        # Assign users to the task
        if assigned_to_users:
            task.assigned_to.set(assigned_to_users)
        
        return task

    def update(self, instance, validated_data):
        """Override update to properly handle ManyToMany fields."""
        assigned_to_users = validated_data.pop("assigned_to", None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update ManyToMany field if provided
        if assigned_to_users is not None:
            instance.assigned_to.set(assigned_to_users)
        
        return instance


class TaskHistorySerializer(serializers.ModelSerializer):
    user = TaskUserSerializer(read_only=True)

    class Meta:
        model = TaskHistory
        fields = ["id", "task", "user", "action", "field_name", "old_value", "new_value", "description", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    sender = TaskUserSerializer(read_only=True, required=False)
    task_id = serializers.IntegerField(source='task.id', read_only=True, required=False)
    task_title = serializers.CharField(source='task.title', read_only=True, required=False)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "event_type",
            "sender",
            "task_id",
            "task_title",
            "action",
            "project",
            "is_read",
            "status",
            "created_at",
            "read_at"
        ]
        read_only_fields = ["created_at", "read_at"]
