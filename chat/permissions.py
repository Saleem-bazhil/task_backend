from user.models import UserProfile


def is_admin_user(user):
    profile = getattr(user, "userprofile", None)
    if profile:
        return profile.role == UserProfile.ADMIN
    return user.is_staff or user.is_superuser


def can_chat_with(source_user, target_user):
    if not source_user.is_authenticated or not target_user.is_active:
        return False
    if source_user.id == target_user.id:
        return False
    source_is_admin = is_admin_user(source_user)
    target_is_admin = is_admin_user(target_user)
    return not (source_is_admin and target_is_admin)
