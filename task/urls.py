from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    TaskAssignableUserListView, 
    TaskDashboardView, 
    Taskview,
    TaskCreatedByMeView,
    TaskAssignedToMeView,
    NotificationViewSet,
    TaskCommentViewSet,
    TaskAttachmentViewSet
)

router = DefaultRouter()
router.register('tasks', Taskview, basename='task')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('comments', TaskCommentViewSet, basename='comment')
router.register('attachments', TaskAttachmentViewSet, basename='attachment')

urlpatterns = [
    path("tasks/dashboard/", TaskDashboardView.as_view(), name="task-dashboard"),
    path("tasks/users/", TaskAssignableUserListView.as_view(), name="task-users"),
    path("tasks/created-by-me/", TaskCreatedByMeView.as_view(), name="tasks-created-by-me"),
    path("tasks/assigned-to-me/", TaskAssignedToMeView.as_view(), name="tasks-assigned-to-me"),
]
urlpatterns += router.urls
