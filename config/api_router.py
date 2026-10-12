from django.conf import settings
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from betterleaf.resumes.views import CompilationViewSet
from betterleaf.resumes.views import ResumeViewSet
from betterleaf.resumes.views import TemplateListView
from betterleaf.resumes.views import WorkspaceView
from betterleaf.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("resumes", ResumeViewSet, basename="resume")
router.register("compilations", CompilationViewSet, basename="compilation")


app_name = "api"
urlpatterns = [
    *router.urls,
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
    path("templates/", TemplateListView.as_view(), name="template-list"),
    path("chat/", include("betterleaf.chat.urls")),
]
