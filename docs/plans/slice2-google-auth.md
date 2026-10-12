# BetterLeaf — Slice 2: Google Sign-In + Guest Workspace Claim

## What this slice does (plain English)

A visitor arrives with no account and starts editing (slice 1 gives them a guest workspace in a cookie). Later they click **"Sign in with Google"**. When that finishes, their guest work — the resumes they already made — automatically becomes attached to their new (or existing) account. Nothing is lost, and nothing is copied.

 Google is the only way to sign in. django-allauth handles the entire Google dance and creates the account for us — we never build a login form or create the user ourselves.

## The whole flow, one step at a time

1. **Guest arrives.** Slice 1's `GET /api/workspace/` creates/returns the guest workspace. We add one line: `request.session["guest_workspace_id"] = str(ws.id)` — "remember this guest's workspace on the server." The workspace ID is stored **server-side in the Django session**, never handed to the browser to send back later, and never baked into Google's URL.
2. **Guest clicks "Sign in with Google."** This is a normal browser navigation (a plain link or form) to `/accounts/google/login/`, then over to Google. Not `fetch`/AJAX — the OAuth flow needs a real page load.
3. **Google sends them back** to `/accounts/google/login/callback/` on our backend. allauth takes over: it checks the `state` token (its own anti-forgery ID), swaps the code for tokens, reads the Google profile, and — if this is a brand-new Google account — **creates the user**; if they've signed in before, it finds the existing user.
4. **allauth logs them in**, which sets the browser's `sessionid` cookie (this is the entire "who is logged in" mechanism — no custom `user_id` cookie, no token).
5. **Our hook fires at the moment of login.** The moment Django logs someone in, it emits a "user logged in" signal. We listen for it: read the stored `guest_workspace_id` out of the session, attach that workspace to the now-known user, and erase the note so it can't be used twice.
6. **allauth redirects** to the frontend (`/resumes`). From here on, the backend decides "which workspace" by looking at the logged-in user — never by trusting an ID the browser sends.

## Ground rules (fixed — do not deviate)

- **allauth owns user creation and login.** We never hand-roll OAuth, never write a login form, never create the `User` ourselves, never call `login()` ourselves.
- **The guest workspace ID lives in the server-side session** (`request.session["guest_workspace_id"]`). Never in a browser-set cookie, never in the `state` parameter. The `state` stays allauth's own random ID.
- **"Who is logged in" is the `sessionid` cookie** set by `login()`. No `user_id` cookie, no client token in this flow.
- **After login, the workspace always comes from the logged-in user**, never from a client-sent ID.

## A note on names (slice 1 vs this slice)

Slice 1's `Workspace` model marks a guest with `user IS NULL` (and a not-yet-claimed `anonymous_token_hash` / `expires_at`). It has no `owner` or `is_guest` columns. This slice keeps slice 1's vocabulary. Mapping:

| The brief's term | Slice 1's actual field | "Still a guest" check |
|---|---|---|
| `owner` | `user` (FK to `users.User`) | `user__isnull=True` |
| `is_guest` | guest ⇔ `user IS NULL` | same, no extra column |

So "claim the guest workspace" becomes `filter(id=ws_id, user__isnull=True)`. **No schema change** — do not add `owner`/`is_guest` unless slice 1 is also rewritten to use them.

## Backend changes

### 1. Register the login hook

`betterleaf/users/apps.py` — the scaffold's `ready()` method is empty. Make it load our hook:

```python
from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "betterleaf.users"
    verbose_name = "Users"  # keep the existing label

    def ready(self):
        from betterleaf.resumes import signals  # noqa: F401
```

Importing `signals` inside `ready()` connects the hook once, at startup. This is the standard Django pattern (Django guards against double-registering).

### 2. The hook itself

New file `betterleaf/resumes/signals.py`:

```python
from allauth.account.signals import user_logged_in
from django.db import transaction
from django.dispatch import receiver

from betterleaf.resumes.models import Workspace


@receiver(user_logged_in)
def claim_guest_workspace(sender, request, user, **kwargs):
    ws_id = request.session.pop("guest_workspace_id", None)
    if not ws_id:
        return
    with transaction.atomic():
        ws = (
            Workspace.objects.select_for_update()
            .filter(id=ws_id, user__isnull=True)
            .first()
        )
        if ws:
            ws.user = user
            ws.anonymous_token_hash = None
            ws.expires_at = None
            ws.save(update_fields=["user", "anonymous_token_hash", "expires_at"])
```

Why this is safe:

- **Only source of truth is the session.** We read `request.session`, never anything the browser sent (query string, body, cookie).
- **Single-use.** `pop` removes the ID as it reads it, so it can only ever be claimed once.
- **Race-proof.** `select_for_update()` locks the row; combined with the `user__isnull=True` filter, two simultaneous logins can't both grab the same workspace — one wins, the second sees it's already owned and skips.
- **Harmless on bad input.** Missing or garbage session value → `pop` returns `None` or the filter matches nothing → no-op, no error.

**Why the "user logged in" hook and not an earlier one:** a brand-new user doesn't exist until allauth saves them. The earlier `pre_social_login` hook runs *before* that save, so `user` has no ID yet and we couldn't attach anything. The `user_logged_in` signal fires *after* allauth has both created and logged in the user — so it covers new signups and returning users with one path.

### 3. Leave user creation alone

`SOCIALACCOUNT_AUTO_SIGNUP` stays `True` (its default): new Google accounts go straight through, no signup form in between. `ACCOUNT_EMAIL_REQUIRED` is `True` by default and Google always supplies the email. The scaffold's existing `SocialAccountAdapter.populate_user` already fills `name`/`first_name`/`last_name` — leave it. (If a future slice needs extra setup on first signup, the place for it is the adapter's `save_user` or the `user_signed_up` signal — **not** this claim hook, which must stay login-agnostic.)

### 4. Configure the Google provider

In `config/settings/base.py`, add:

```python
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email", "openid"],
    },
}
```

And add `"allauth.socialaccount.providers.google"` to `THIRD_PARTY_APPS`. Then register the Google "SocialApp" (client ID + secret) through Django admin at `/admin/socialaccount/socialapp/` — leave the `key` field blank. No secrets live in the repo.

### 5. Point login at the frontend

`LOGIN_REDIRECT_URL` currently points at `users:redirect`. Point it at `/resumes` (the SPA is same-origin thanks to slice 1's `rewrites`). allauth's `next` parameter keeps working for deep links.

### 6. Workspaces come from the logged-in user

Slice 1's `get_workspace` already resolves "the signed-in user's workspace" (`Workspace.objects.filter(user=user).order_by("created_at").first()`, creating one if missing). No change needed — this is the post-login source of truth and satisfies "never trust a client-sent ID."

## Settings & config checklist

| Setting | Value | Why |
|---|---|---|
| `SESSION_COOKIE_SAMESITE` | `Lax` (set it explicitly in `base.py`) | The OAuth callback is a top-level navigation; `Lax` lets the `sessionid` set on the callback stick. (allauth ≥ 0.62 also tolerates `Strict`.) |
| One host | no `localhost`⇄`127.0.0.1`, no `www`⇄bare mixing | the session cookie and the OAuth redirect must agree on a single origin. |
| `CSRF_TRUSTED_ORIGINS` | only if the SPA is a separate origin | trusts the SPA origin for unsafe requests. |
| CORS | none needed (slice 1's `rewrites` already proxy `/api`+`/media`) | only relevant for a separate-origin frontend, which is not our setup. |
| Google redirect URI | `https://<backend-host>/accounts/google/login/callback/` | registered in the Google Cloud Console OAuth client. |
| `ACCOUNT_EMAIL_VERIFICATION` | `mandatory` (already set) | new Google users must verify email before `login()` completes; the session (and thus the pending claim) survives that detour. Confirm the verification redirect chain does not clear the session. |

## Security checklist (what the code guarantees)

- Workspace ID read **only** from the server session — never from the request body/query/cookie.
- Claim filters on `user__isnull=True` inside a transaction with `select_for_update` — no double-claim, no race.
- Workspace IDs are random UUIDs (from slice 1).
- `session.pop(...)` → single-use, consumed exactly once.
- No `user_id` cookie, ever. The `sessionid` set by `login()` is the whole story.

## Known limitations (acceptable — document them)

- **Same browser only.** The guest workspace ID lives in that browser's session. Signing in from another device — or after clearing cookies — won't link; there's nothing to link. Logging out also flushes the session and drops the pending link.
- **Returning user gets the guest as an extra workspace.** If someone with an existing account signs in from a browser holding a guest workspace, the guest is simply attached to their account as an *additional* workspace (they now have two). **Decision needed:** keep "attach as additional" (this plan's default) or merge the guest's resumes into their existing workspace. Merging is a later enhancement, not this slice.
- **In-app browsers** (Instagram, Facebook) may break cookies and thus Google OAuth + the session link. Not handled.

## Fallback (only if the session can't be shared across a cross-site frontend)

If the SPA ever runs on a genuinely different site from the backend (so the session cookie can't round-trip), do **not** stuff the workspace ID into `state`. Instead save `{state_id: workspace_id}` server-side (DB or cache, short TTL), keyed by allauth's `state`, and look it up on the callback. Out of scope for our same-site setup — do not implement now.

## Frontend (Next.js)

- "Sign in with Google" is a plain `<a href="/accounts/google/login/">` (or a form/window navigation) — **never** `fetch`/XHR; OAuth needs a real page load.
- The guest bootstrap (`GET /api/workspace/`) is unchanged; the one added session write (step 1) means the pending link is already primed at first visit.
- After the allauth redirect lands on `/resumes`, do nothing special — the backend already resolves the workspace from the logged-in user. There is no attach endpoint to call.

## Critical files & anchors

- `betterleaf/users/apps.py` — `ready()` imports `betterleaf.resumes.signals`.
- `betterleaf/resumes/signals.py` (new) — the login hook.
- `betterleaf/resumes/models.py` — `Workspace` (existing; `user`, `anonymous_token_hash`, `expires_at`). No schema change.
- `betterleaf/resumes/views.py` — `WorkspaceView.GET` gains the one `request.session["guest_workspace_id"]` write (slice 1 file).
- `betterleaf/resumes/auth.py` — `get_workspace` already derives from the user (no change).
- `config/settings/base.py` — `SOCIALACCOUNT_PROVIDERS`, `THIRD_PARTY_APPS` += google provider, `SESSION_COOKIE_SAMESITE`, `LOGIN_REDIRECT_URL` → `/resumes`.

## Verify each scenario

- **New user:** incognito → open the app (guest workspace created, ID in session) → "Sign in with Google" as a brand-new account → land on `/resumes` → the *same* resumes from before are there, and in the DB that workspace now has `user` set and `anonymous_token_hash` cleared.
- **Returning user:** same, but with an existing Google account → the guest workspace attaches to that account.
- **Missing/tampered session:** no `guest_workspace_id` (or a nonsense value) → no error, no attach; the user just gets their normal workspace.
- **Double-claim:** two logins racing for the same workspace → exactly one wins, the other is a no-op (`select_for_update` + `user__isnull`).
- **Logout then login:** logging out flushes the session, so the pending link is gone; a later login does not resurrect the guest workspace.
- **Unit test:** seed `request.session["guest_workspace_id"]`, call `claim_guest_workspace` with a stub `user`/`request`, assert `user`/`anonymous_token_hash`/`expires_at` updated; a second test asserts an already-claimed workspace is left untouched.

## Assumptions & contingencies

- **Email verification detour:** with `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, a first-time Google user must verify email before `login()` completes. The session (holding `guest_workspace_id`) survives that redirect, so the claim fires only after verification. If the verification endpoints are configured to flush the session, this breaks — confirm they reuse the same `sessionid` and don't clear it. (In local dev, use the console email backend so the verification link is reachable.)
- **`SOCIALACCOUNT_AUTO_SIGNUP` stays `True`.** Even if a later slice demands a signup form, the claim still works — `user_logged_in` fires after the form finishes, and the session survives.
- **Same-site assumption** holds via slice 1's `rewrites`. A cross-site deployment needs the fallback (state→workspace mapping) plus CORS / `CSRF_TRUSTED_ORIGINS` / `SESSION_COOKIE_SAMESITE="None"`.
