from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import AuthUserSerializer, LoginSerializer, RegisterSerializer, UpdateProfileSerializer
from .models import UserProfile


class AuthRateThrottle(AnonRateThrottle):
    """Stricter throttle for authentication endpoints."""
    rate = "5/minute"


def build_auth_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": AuthUserSerializer(user).data,
    }


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(build_auth_response(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(build_auth_response(serializer.validated_data), status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(AuthUserSerializer(request.user).data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AuthUserSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AuthUserSerializer(request.user).data, status=status.HTTP_200_OK)


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class IsAdminUser(permissions.BasePermission):
    """Allow only users with admin role or staff."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        profile = getattr(request.user, 'userprofile', None)
        return profile and profile.role == 'admin'


class AdminUserManageView(APIView):
    """Admin-only: PATCH or DELETE any user by ID."""
    permission_classes = [IsAdminUser]

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def patch(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Update basic user fields
        for field in ('first_name', 'last_name', 'email'):
            if field in request.data:
                setattr(user, field, request.data[field])
        
        # Update password if provided
        new_password = request.data.get('password', '').strip()
        if new_password:
            user.set_password(new_password)

        user.save()

        # Update role if provided
        new_role = request.data.get('role')
        if new_role in ('employee', 'admin'):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = new_role
            profile.save(update_fields=['role'])

        return Response(AuthUserSerializer(user).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Prevent deleting yourself
        if user.pk == request.user.pk:
            return Response({'detail': 'You cannot delete your own account.'}, status=status.HTTP_400_BAD_REQUEST)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
