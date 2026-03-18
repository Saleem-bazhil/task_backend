from django.conf import settings
from django.db import models


class ChatRoom(models.Model):
    user_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chatrooms_as_user_one",
    )
    user_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chatrooms_as_user_two",
    )
    room_id = models.SlugField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user_one", "user_two"],
                name="unique_chatroom_pair",
            ),
            models.CheckConstraint(
                check=~models.Q(user_one=models.F("user_two")),
                name="prevent_self_chatroom",
            ),
        ]

    def save(self, *args, **kwargs):
        low_user, high_user = sorted([self.user_one_id, self.user_two_id])
        self.user_one_id = low_user
        self.user_two_id = high_user
        self.room_id = f"{low_user}_{high_user}"
        super().save(*args, **kwargs)

    def includes_user(self, user):
        return user.id in {self.user_one_id, self.user_two_id}

    def get_other_user(self, user):
        return self.user_two if user.id == self.user_one_id else self.user_one

    def __str__(self):
        return self.room_id


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"
