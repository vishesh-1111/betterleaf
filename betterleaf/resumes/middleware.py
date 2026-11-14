from betterleaf.resumes.auth import resolve_workspace

API_PREFIX = "/api/"


class WorkspaceMiddleware:
    """Attach ``request.workspace`` to API requests.

    The signed-in user's workspace, else the guest workspace named by the
    ``bl_session`` cookie, else ``None``. It never creates a guest workspace;
    the upload flow does that through ``get_or_create_workspace``.

    Must sit after ``AuthenticationMiddleware`` so ``request.user`` is set.
    Session login (allauth) is the only auth mechanism, so ``request.user`` is
    already final here. Don't add a DRF-only scheme such as token auth without
    revisiting this, since DRF authenticates later, inside the view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(API_PREFIX):
            request.workspace = resolve_workspace(request)
        else:
            request.workspace = None
        return self.get_response(request)
