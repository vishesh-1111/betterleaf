from django.urls import path

from betterleaf.resumes.views import UploadPdfView
from betterleaf.resumes.views import UserStatusView
from betterleaf.resumes.views import WorkspaceView

app_name = "resumes"
urlpatterns = [
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
    path("user-status/", UserStatusView.as_view(), name="user-status"),
    path("upload-pdf/", UploadPdfView.as_view(), name="upload-pdf"),
]
