from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("task.urls")),
    path("api/", include("user.urls")),
    path("api/", include("chat.urls")),
]

# Always serve media files. In production with S3, Django's storage
# backend returns absolute S3 URLs so these patterns won't match;
# this line only matters for local dev / non-S3 deployments.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
