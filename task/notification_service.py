"""
Notification Service for Task Tracker.
Handles creation and real-time broadcasting of notifications via WebSocket.
"""

from django.contrib.auth.models import User
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import json

from .models import Task, Notification, TaskComment
from .serializers import NotificationSerializer


def create_and_broadcast_notification(
    user: User,
    event_type: str,
    title: str,
    message: str = "",
    sender: User = None,
    task: Task = None,
    action: str = "",
    project: str = "Task Tracker",
    status_msg: str = "info"
):
    """
    Create a notification and broadcast it to the user via WebSocket.
    
    Args:
        user: Recipient user
        event_type: One of 'task_assigned', 'task_updated', 'comment_added', etc.
        title: Notification title
        message: Detailed message
        sender: User who initiated the action
        task: Related task object
        action: Legacy action field for backwards compatibility
        project: Project name
        status_msg: Status type ('success', 'info', 'warning', 'error')
    """
    with transaction.atomic():
        notification = Notification.objects.create(
            user=user,
            sender=sender,
            task=task,
            event_type=event_type,
            title=title,
            message=message,
            action=action or title,
            project=project,
            status=status_msg
        )
        
        # Broadcast notification to user via WebSocket
        broadcast_notification_to_user(notification)
        
        return notification


def broadcast_notification_to_user(notification: Notification):
    """
    Broadcast notification to a specific user via WebSocket.
    Uses a notification group per user: notification_{user_id}
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    serialized = NotificationSerializer(notification).data
    
    # Send to user's notification group
    async_to_sync(channel_layer.group_send)(
        f"notification_{notification.user_id}",
        {
            "type": "notification.message",
            "notification": serialized,
        },
    )


def notify_task_assigned(task: Task, assigned_user: User, assigner: User = None):
    """Notify user when task is assigned to them."""
    message = f"{assigner.get_full_name() or assigner.username} assigned you a task: {task.title}"
    create_and_broadcast_notification(
        user=assigned_user,
        event_type="task_assigned",
        title=assigner.username if assigner else "System",
        message=message,
        sender=assigner,
        task=task,
        action=f"assigned you a new task: '{task.title[:30]}'",
        status_msg="success"
    )


def notify_task_updated(task: Task, updater: User, change_type: str = "status"):
    """
    Notify all task participants when task is updated.
    
    Args:
        task: Updated task
        updater: User who made the update
        change_type: Type of change ('status', 'priority', 'due_date', 'description')
    """
    # Get all task participants (creator + assigned users)
    participants = set()
    if task.user:
        participants.add(task.user)
    
    for assigned_user in task.assigned_to.all():
        participants.add(assigned_user)
    
    # Remove the updater from participants
    participants.discard(updater)
    
    for participant in participants:
        message = f"{updater.get_full_name() or updater.username} updated {change_type} on task: {task.title}"
        create_and_broadcast_notification(
            user=participant,
            event_type="task_updated",
            title=f"{updater.username} updated task",
            message=message,
            sender=updater,
            task=task,
            action=f"updated task state: '{task.title[:30]}'",
            status_msg="info"
        )


def notify_comment_added(comment: TaskComment, commenter: User):
    """
    Notify all task participants when a comment is added.
    
    Args:
        comment: The new comment
        commenter: User who made the comment
    """
    task = comment.task
    
    # Get all task participants
    participants = set()
    if task.user:
        participants.add(task.user)
    
    for assigned_user in task.assigned_to.all():
        participants.add(assigned_user)
    
    # Remove the commenter
    participants.discard(commenter)
    
    message = f"{commenter.get_full_name() or commenter.username} commented on task: {task.title}"
    preview = comment.content[:100]
    
    for participant in participants:
        create_and_broadcast_notification(
            user=participant,
            event_type="comment_added",
            title=f"{commenter.username} commented",
            message=message,
            sender=commenter,
            task=task,
            action=f"commented on task: '{task.title[:30]}'",
            status_msg="info"
        )


def notify_task_completed(task: Task, completer: User):
    """Notify all task participants when task is marked as completed."""
    participants = set()
    if task.user and task.user != completer:
        participants.add(task.user)
    
    for assigned_user in task.assigned_to.all():
        if assigned_user != completer:
            participants.add(assigned_user)
    
    for participant in participants:
        message = f"{completer.get_full_name() or completer.username} completed task: {task.title}"
        create_and_broadcast_notification(
            user=participant,
            event_type="task_completed",
            title=f"Task completed",
            message=message,
            sender=completer,
            task=task,
            action=f"completed task: '{task.title[:30]}'",
            status_msg="success"
        )


def notify_users(user_ids: list, event_type: str, title: str, message: str, 
                 sender: User = None, task: Task = None):
    """
    Generic function to notify multiple users.
    
    Args:
        user_ids: List of user IDs to notify
        event_type: Type of notification event
        title: Notification title
        message: Detailed message
        sender: User who initiated the action
        task: Related task object
    """
    users = User.objects.filter(id__in=user_ids)
    for user in users:
        create_and_broadcast_notification(
            user=user,
            event_type=event_type,
            title=title,
            message=message,
            sender=sender,
            task=task
        )
