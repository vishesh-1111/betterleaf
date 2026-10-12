from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ResumesConfig(AppConfig):
    name = "betterleaf.resumes"
    verbose_name = _("Resumes")

    def ready(self) -> None:
        # Import the module so its @receiver(user_logged_in) handlers register.
        from betterleaf.resumes import signals  # noqa: F401
