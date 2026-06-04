from rest_framework.permissions import BasePermission

from .models import Profile


def user_role(user):
    profile, _created = Profile.objects.get_or_create(
        user=user,
        defaults={'full_name': user.get_full_name() or user.email or user.username},
    )
    return getattr(profile, 'role', 'buyer')


class IsVerifiedUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_staff or user_role(request.user) == 'admin')
