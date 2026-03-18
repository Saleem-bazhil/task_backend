from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import TaskDashboardView, Taskview

router = DefaultRouter()
router.register('tasks', Taskview, basename='task')

urlpatterns = [
    path("tasks/dashboard/", TaskDashboardView.as_view(), name="task-dashboard"),
]
urlpatterns += router.urls
