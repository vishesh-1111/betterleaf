from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialAccount
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from betterleaf.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def post_login(
        self,
        request: HttpRequest,
        user: typing.Any,
        *,
        email_verification: str,
        signal_kwargs: dict[str, typing.Any] | None,
        email: str | None,
        signup: bool,
        redirect_url: str | None,
    ):
        # Let allauth build the redirect and fire ``user_logged_in`` (whose
        # receivers read the ``bl_session`` cookie to claim the anonymous
        # workspace); then clear the cookie so a later logout does not revive
        # a stale anonymous session.
        response = super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )
        response.delete_cookie("bl_session")
        return response

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """Redirect logins back to the frontend so the SPA can resume.

        The only login path is the Google OAuth flow initiated by the frontend
        download button. The ``?next`` param carries a cross-origin URL
        (``FRONTEND_URL``) that ``is_safe_url`` rejects, so allauth falls back
        to this method; return to the frontend with ``?download=true`` so the
        SPA resumes the requested download.
        """
        return f"{settings.FRONTEND_URL.rstrip('/')}/?download=true"

    def get_signup_redirect_url(self, request: HttpRequest) -> str:
        """Redirect fresh signups (auto-signup via Google) back to the frontend.

        allauth uses this for new accounts created by the social login — the
        default ``SIGNUP_REDIRECT_URL`` resolves to ``users:redirect``. Return
        the same frontend URL as ``get_login_redirect_url``.
        """
        return f"{settings.FRONTEND_URL.rstrip('/')}/?download=true"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user

    def get_connect_redirect_url(
        self,
        request: HttpRequest,
        socialaccount: SocialAccount,
    ) -> str:
        """Redirect back to the frontend after connecting a social account.

        Runs for the connect flow only (an already-logged-in user linking a
        provider); the login flow is handled by ``AccountAdapter``.
        """
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        return f"{frontend_url}/?download=true"
