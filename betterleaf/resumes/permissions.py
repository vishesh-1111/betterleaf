from rest_framework.permissions import BasePermission


class HasWorkspace(BasePermission):
    """Requires ``request.workspace`` (set by ``WorkspaceMiddleware``)."""

    message = "No active workspace; upload a resume to get started."

    def has_permission(self, request, view):
        return getattr(request, "workspace", None) is not None
