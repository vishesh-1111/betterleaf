from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ResumesConfig(AppConfig):
    name = "betterleaf.resumes"
    verbose_name = _("Resumes")
