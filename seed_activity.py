import os
import sys
import django
from datetime import timedelta
from django.utils import timezone
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'task_backend.settings')
django.setup()

from task.models import Task

try:
    user = User.objects.first()
    now = timezone.now()

    if not user:
        print("No users found to seed.")
    else:
        for i in range(1, 7):
            past_date = now - timedelta(days=i)
            
            # create [1-3] created tasks for this day
            created_count = random.randint(1, 3)
            for j in range(created_count):
                task = Task.objects.create(
                    title=f"Archived Task {i}-{j}",
                    description="Dummy text",
                    status="completed" if random.random() > 0.5 else "in_progress",
                    user=user,
                    due_date=past_date.date() + timedelta(days=2)
                )
                # Intentionally backdate created_at and updated_at
                Task.objects.filter(id=task.id).update(created_at=past_date, updated_at=past_date)
            
            # create [0-2] specifically completed on this day
            completed_count = random.randint(0, 2)
            for j in range(completed_count):
                t2 = Task.objects.create(
                    title=f"Resolution Task {i}-{j}",
                    description="Dummy text",
                    status="completed",
                    user=user,
                    due_date=past_date.date()
                )
                Task.objects.filter(id=t2.id).update(created_at=past_date - timedelta(days=2), updated_at=past_date)

        print("Seeded successfully!")
except Exception as e:
    print("Error:", e)
