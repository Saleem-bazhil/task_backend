from django.urls import path
from .views import MessageViewSet

urlpatterns = [
    path("messages/<str:room>/", MessageViewSet.as_view({"get": "list"})),
]