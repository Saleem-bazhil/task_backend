from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0001_initial"),
        ("chat", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="Message"),
        migrations.CreateModel(
            name="ChatRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("room_id", models.SlugField(editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user_one",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chatrooms_as_user_one", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "user_two",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chatrooms_as_user_two", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="chatroom",
            constraint=models.UniqueConstraint(fields=("user_one", "user_two"), name="unique_chatroom_pair"),
        ),
        migrations.AddConstraint(
            model_name="chatroom",
            constraint=models.CheckConstraint(condition=~models.Q(user_one=models.F("user_two")), name="prevent_self_chatroom"),
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField()),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "receiver",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_messages", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "room",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="chat.chatroom"),
                ),
                (
                    "sender",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_messages", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["timestamp", "id"]},
        ),
    ]
