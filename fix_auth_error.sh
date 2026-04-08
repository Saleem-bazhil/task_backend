#!/bin/bash
# Fix script for Axios 500 error

cd task_backend

echo "🔧 Step 1: Check for database migrations..."
python manage.py showmigrations user

echo ""
echo "🔧 Step 2: Apply any pending migrations..."
python manage.py migrate

echo ""
echo "🔧 Step 3: Fix existing user profiles..."
python manage.py shell << EOF
from user.models import UserProfile
from django.contrib.auth.models import User

# Fix any profiles with old role choices
for profile in UserProfile.objects.all():
    if profile.role == "employee":
        profile.role = "contributor"
        profile.save()
        print(f"✅ Updated {profile.user.username}: employee → contributor")
    elif profile.role not in ["admin", "manager", "employee", "contributor"]:
        profile.role = "contributor"
        profile.save()
        print(f"✅ Fixed {profile.user.username}: invalid role → contributor")

print("✅ All profiles updated!")
EOF

echo ""
echo "✅ Done! Restart your Django server and try logging in again."
echo ""
echo "To restart the server:"
echo "  daphne -b 0.0.0.0 -p 8000 atrack.asgi:application"
