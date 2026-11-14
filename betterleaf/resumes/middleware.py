from betterleaf.resumes.auth import resolve_workspace

API_PREFIX = "/api/"


class WorkspaceMiddleware:
    """Attach ``request.workspace`` to API requests.

    The signed-in user's workspace, else the guest workspace named by the
    ``bl_session`` cookie, else ``None``. It never creates a guest workspace;
    the upload flow does that through ``get_or_create_workspace``.

    Must sit after ``AuthenticationMiddleware`` so ``request.user`` is set.
    Only Django session auth is seen here: a DRF token-authenticated caller
    is authenticated later, inside the view, so appears as a guest.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(API_PREFIX):
            request.workspace = resolve_workspace(request)
        else:
            request.workspace = None
        return self.get_response(request)
