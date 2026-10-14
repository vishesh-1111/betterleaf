from django.conf import settings
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from betterleaf.resumes.views import CompilationViewSet
from betterleaf.resumes.views import ProposalViewSet
from betterleaf.resumes.views import ResumeViewSet
from betterleaf.resumes.views import TemplateListView
from betterleaf.users.api.views import UserViewSet
from betterleaf.users.api.views import auth_status

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("resumes", ResumeViewSet, basename="resume")
router.register("compilations", CompilationViewSet, basename="compilation")
router.register("proposals", ProposalViewSet, basename="proposal")


app_name = "api"
urlpatterns = [
    path("users/auth-status/", auth_status, name="auth-status"),
    *router.urls,
    path("templates/", TemplateListView.as_view(), name="template-list"),
    path("chat/", include("betterleaf.chat.urls")),
]
