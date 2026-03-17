from rest_framework.viewsets import ReadOnlyModelViewSet
from .models import Message
from .serializers import MessageSerializer

class MessageViewSet(ReadOnlyModelViewSet):
    serializer_class = MessageSerializer

    def get_queryset(self):
        room = self.kwargs["room"]
        return Message.objects.filter(room=room).order_by("timestamp")