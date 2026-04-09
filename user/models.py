from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    ADMIN = "admin"
    EMPLOYEE = "employee"
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    
    ROLE_CHOICES = (
        (ADMIN, "Admin"),
        (MANAGER, "Manager"),
        (EMPLOYEE, "Employee"),
        (CONTRIBUTOR, "Contributor"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default=CONTRIBUTOR)
    
    # Allow all users to participate in collaborative tasks regardless of role
    bio = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    class Meta:
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
