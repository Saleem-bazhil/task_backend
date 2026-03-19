from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import serializers

from .models import UserProfile


class AuthUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role"]

    def get_role(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.role if profile else UserProfile.EMPLOYEE


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        required=False,
        default=UserProfile.EMPLOYEE,
    )

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name", "email", "role"]

    def validate_role(self, value):
        request = self.context.get("request")
        if value == UserProfile.ADMIN and (not request or not request.user.is_authenticated or not getattr(request.user, "userprofile", None) or request.user.userprofile.role != UserProfile.ADMIN):
            raise serializers.ValidationError("Only admins can create admin users.")
        return value

    def create(self, validated_data):
        role = validated_data.pop("role", UserProfile.EMPLOYEE)
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        user.userprofile.role = role
        user.userprofile.save(update_fields=["role"])
        return user


class UpdateProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role"]
        read_only_fields = ["username", "role"]

    def get_role(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.role if profile else UserProfile.EMPLOYEE


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data["username"].strip()
        password = data["password"]
        user = authenticate(username=username, password=password)
        if not user:
            raise AuthenticationFailed("Invalid username or password.")
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")
        return user
