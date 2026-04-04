from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import TaskAssignableUserListView, TaskDashboardView, Taskview, NotificationViewSet

router = DefaultRouter()
router.register('tasks', Taskview, basename='task')
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path("tasks/dashboard/", TaskDashboardView.as_view(), name="task-dashboard"),
    path("tasks/users/", TaskAssignableUserListView.as_view(), name="task-users"),
]
urlpatterns += router.urls
