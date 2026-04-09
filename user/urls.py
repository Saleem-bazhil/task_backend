from django.urls import path

from .views import LoginView, MeView, RefreshView, RegisterView, AdminUserManageView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="token-refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/users/<int:pk>/", AdminUserManageView.as_view(), name="admin-user-manage"),
]
