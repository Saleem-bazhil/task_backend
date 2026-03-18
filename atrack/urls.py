from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("task.urls")),
    path("api/", include("user.urls")),
    path("api/", include("chat.urls")),
]
