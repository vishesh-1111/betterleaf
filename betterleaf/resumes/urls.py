from django.urls import path

from betterleaf.resumes.views import WorkspaceView

app_name = "resumes"
urlpatterns = [
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
]
