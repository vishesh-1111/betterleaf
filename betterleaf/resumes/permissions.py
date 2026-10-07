from rest_framework.permissions import BasePermission

from betterleaf.resumes.auth import get_workspace


class HasWorkspace(BasePermission):
    message = "No active workspace; create one via GET /api/workspace/."

    def has_permission(self, request, view):
        return get_workspace(request) is not None
