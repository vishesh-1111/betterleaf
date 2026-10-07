# BetterLeaf — Slice 1: Live LaTeX Compile + PDF Preview + Download

## Context

BetterLeaf is an AI-assisted LaTeX editor for resume development. This plan delivers **slice 1 only**: a user types LaTeX and sees a live-compiled PDF preview that tracks the source, and can download that PDF. AI edit, JD tailoring, and resume upload→convert are later slices and are not touched here.

The backend is the existing cookiecutter-django scaffold at `/home/vishesh/betterleaf` (Django 6.0.8, DRF, Celery+Redis, Postgres, allauth). The frontend is a new Next.js app. A user owns multiple resumes; there is no version history (current version only).

A template is a **directory of LaTeX source files** (a starter `.tex` and, if styled, a `.cls` class file) whose compilation is verified against Tectonic. The first and only shipping template is **Jake's Resume**. The `.tex`→`.cls` distinction: a `.cls` file is a reusable LaTeX class (the "layout engine") loaded via `\documentclass{...}`; a `.tex` is content. Jake's Resume is a flat `article` + preamble, so it ships as a self-contained `starter.tex` (no `.cls`). Future templates that need a reusable class add a `.cls`.

Load-bearing decisions (fixed): server-side compilation via a pinned **Tectonic 0.16.9** binary run by **Celery**; **Next.js SPA** with Django as API-only; result delivery by **polling** a status endpoint; auth via the existing **DRF TokenAuthentication**.

## Approach

### Backend (Django)

**1. Install Tectonic into the Docker images.**

Add a pinned Tectonic static binary to both `compose/local/django/Dockerfile` and `compose/production/django/Dockerfile`. In the local Dockerfile, add `ca-certificates curl tar` to the first `apt-get install` list (the base `uv:python3.14-bookworm-slim` image does not guarantee `curl`). Then, after the final `uv sync`, add:

```dockerfile
ARG TECTONIC_VERSION=0.16.9
RUN curl -fSL -o /tmp/tectonic.tar.gz \
      "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    && echo "60b13a0826ae7ad9ce34b4a2df06bff2cfcfa6dda8a915477c0cbb84e1a4a902  /tmp/tectonic.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && chmod +x /usr/local/bin/tectonic \
    && rm /tmp/tectonic.tar.gz
```

For `compose/production/django/Dockerfile`, add the same `RUN` block into the `python:3.14-slim-bookworm` run stage (the stage named `python-run-stage`) after the `apt-get` block, and add `ca-certificates curl` to that stage's `apt-get install` list.

SHA-256 `60b13a…4a902` is the verified hash for the `x86_64-unknown-linux-musl` asset of Tectonic 0.16.9 (source: Oleafly's `scripts/fetch-tectonic.sh`).

**2. Give the Celery worker a persistent Tectonic cache.**

Tectonic downloads its TeX bundle on first compile; cache it so later compiles are offline. In `docker-compose.local.yml`, add a named volume `betterleaf_local_tectonic_cache` and, on the `django` anchor service (so `celeryworker` inherits it), add:

```yaml
environment:
  TECTONIC_CACHE_DIR: /tectonic-cache
```
and to that service's `volumes:` list `betterleaf_local_tectonic_cache:/tectonic-cache`. Mirror the env var + a writable volume for the production celery worker service in `docker-compose.production.yml`.

**3. Create the `resumes` app and models.**

`python manage.py startapp` is not run; create `betterleaf/resumes/` with the files below. Add `"betterleaf.resumes"` to `LOCAL_APPS` in `config/settings/base.py`.

`betterleaf/resumes/models.py`:

```python
import uuid
from slugify import slugify
from django.conf import settings
from django.db import models


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    template = models.CharField(max_length=50)  # slug key into TEMPLATE_CATALOG
    main_tex = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title) or "resume"
        candidate, n = base, 1
        while Resume.objects.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate


class Compilation(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="compilations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    pdf = models.FileField(upload_to="resumes/pdfs/%Y/%m/", null=True, blank=True)
    log = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

Generate and commit the migration (`makemigrations resumes`).

**4. Template catalog + the single Jake's Resume template.**

Create `betterleaf/resumes/catalog.py`:

```python
from dataclasses import dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "template_src"


@dataclass(frozen=True)
class ResumeTemplate:
    slug: str
    name: str
    starter_tex: Path
    cls_path: Path | None = None  # None = starter.tex is self-contained (no class file)
    attribution: str = ""  # license/provenance note, rendered nowhere in slice 1


def _tex_only(slug: str, name: str) -> ResumeTemplate:
    d = SRC_DIR / slug
    return ResumeTemplate(slug, name, d / "starter.tex", None, "MIT (sb2nov/resume)")


TEMPLATE_CATALOG = {
    "jakes": _tex_only("jakes", "Jake's Resume"),
}
```

Author one compilable template, `betterleaf/resumes/template_src/jakes/starter.tex`, ported from the canonical Jake's Resume source (`sb2nov/resume` → `sourabh_bajaj_resume.tex`, MIT-licensed):

- Keep the `\documentclass[letterpaper,11pt]{article}` preamble and all custom commands verbatim: `\resumeItem`, `\resumeHeading`, `\resumeSubheading`, `\resumeSubSubheading`, `\resumeItemPlain`, and the `\titleformat{\section}` section styling with `\titlerule`.
- Packages to keep (all present in Tectonic's bundle): `fullpage`, `titlesec`, `color`, `enumitem`, `hyperref`, `fancyhdr`, `babel`, `tabularx`.
- **Remove the pdfTeX-specific lines** so it compiles under Tectonic's XeTeX engine (XeTeX rejects them): `\input{glyphtounicode}` and `\pdfgentounicode=1`.
- Replace the original bio with placeholder body content (a fake name/contact, `\section{Experience}` / `\section{Education}` / `\section{Technical Skills}` each with one `\resumeSubheading` or `\resumeItem` example) so a fresh resume renders something sensible but is obviously a template.

`starter.tex` must compile under `pdflatex`/Tectonic; the pdfTeX lines are the only removals required. Acceptance: `tectonic starter.tex` in `template_src/jakes/` produces a PDF whose first bytes are `%PDF-`.

**5. Celery compile task.**

`betterleaf/resumes/tasks.py`:

```python
import shutil
import subprocess
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation

TECTONIC_TIMEOUT = 30


@shared_task
def compile_resume(compilation_id: str) -> None:
    try:
        compilation = Compilation.objects.select_related("resume").get(id=compilation_id)
    except Compilation.DoesNotExist:
        return
    resume = compilation.resume
    compilation.status = Compilation.Status.RUNNING
    compilation.save(update_fields=["status"])
    template = TEMPLATE_CATALOG[resume.template]
    tmpdir = Path(tempfile.mkdtemp(prefix="betterleaf-compile-"))
    try:
        (tmpdir / "main.tex").write_text(resume.main_tex)
        if template.cls_path is not None:
            shutil.copy(template.cls_path, tmpdir / "resume.cls")
        proc = subprocess.run(
            ["tectonic", "--outdir", str(tmpdir), "main.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=TECTONIC_TIMEOUT,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
        pdf_path = tmpdir / "main.pdf"
        if proc.returncode == 0 and pdf_path.exists():
            compilation.pdf.save(f"{resume.slug}.pdf", ContentFile(pdf_path.read_bytes()), save=False)
            compilation.status = Compilation.Status.SUCCEEDED
        else:
            compilation.status = Compilation.Status.FAILED
        compilation.log = log
        compilation.finished_at = timezone.now()
        compilation.save()
    except subprocess.TimeoutExpired:
        compilation.status = Compilation.Status.FAILED
        compilation.log = f"Compilation timed out after {TECTONIC_TIMEOUT}s."
        compilation.finished_at = timezone.now()
        compilation.save()
    except KeyError:
        compilation.status = Compilation.Status.FAILED
        compilation.log = f"Unknown template: {resume.template}"
        compilation.finished_at = timezone.now()
        compilation.save()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

The `TECTONIC_CACHE_DIR` env var set on the worker (step 2) makes Tectonic reuse its downloaded bundle. The task stores the raw Tectonic stdout+stderr as `log`; no structured log parser is needed for slice 1 (the frontend renders the raw log).

**6. Serializers, viewsets, templates endpoint, router.**

`betterleaf/resumes/serializers.py`:

- `TemplateSerializer` — fields `slug`, `name`.
- `ResumeSerializer` — `id`, `title`, `slug`, `template`, `main_tex`, `updated_at`, `latest_pdf_url` (SerializerMethodField returning the `.pdf.url` of the newest `Compilation` with `status=SUCCEEDED` for this resume, or `None`).
- `ResumeListSerializer` — `id`, `title`, `slug`, `template`, `updated_at` (omit `main_tex` and `latest_pdf_url`).
- `CompilationSerializer` — `id`, `status`, `pdf_url` (`.pdf.url` or `None`), `log`, `created_at`, `finished_at`.

`betterleaf/resumes/views.py`:

- `TemplateListView(APIView)` — `GET`, returns `TemplateSerializer(TEMPLATE_CATALOG.values(), many=True)`.
- `ResumeViewSet(viewsets.ModelViewSet)` — `queryset` scoped to `self.request.user`; `get_serializer_class` returns `ResumeListSerializer` for `list`, `ResumeSerializer` otherwise; `perform_create` sets `owner` and seeds `main_tex` from `TEMPLATE_CATALOG[template].starter_tex.read_text()`. Custom actions:
  - `compile` (`POST /api/resumes/{id}/compile/`, `@action(detail=True, methods=["post"])`): if `main_tex` is blank return 400 with message `"Resume has no content."`; create `Compilation(resume=..., status=QUEUED)`, call `compile_resume.delay(str(compilation.id))`, return 201 with `{"id": str(compilation.id), "status": "queued"}`.
  - `download` (`GET /api/resumes/{id}/download/`, `@action(detail=True, methods=["get"])`): return `FileResponse` of the newest `SUCCEEDED` compilation's `.pdf` (open via `.pdf.open("rb")`), `Content-Disposition: attachment; filename="{resume.slug}.pdf"`, content type `application/pdf`; 404 `{"detail": "No compiled PDF available."}` if none.
- `CompilationViewSet(viewsets.ReadOnlyModelViewSet)` — queryset `Compilation.objects.filter(resume__owner=self.request.user)`, serializer `CompilationSerializer`.

Validate `template` against `TEMPLATE_CATALOG` in `ResumeSerializer.validate_template` (reject unknown slug with a `ValidationError`). All views inherit `IsAuthenticated` from the scaffold's `DEFAULT_PERMISSION_CLASSES`.

`betterleaf/resumes/urls.py` is not needed; register in `config/api_router.py`:

```python
from django.urls import path
from betterleaf.resumes.views import CompilationViewSet, ResumeViewSet, TemplateListView

router.register("resumes", ResumeViewSet, basename="resume")
router.register("compilations", CompilationViewSet, basename="compilation")

urlpatterns = router.urls + [path("templates/", TemplateListView.as_view(), name="template-list")]
```

The existing `app_name = "api"` and `router.register("users", UserViewSet)` stay.

**7. Backend tests.**

In `betterleaf/resumes/tests.py` (pytest-django, token auth via `rest_framework.authtoken`):

- `test_compile_produces_pdf`: create a `Resume` with `template="jakes"` and `main_tex` = the Jake's `starter.tex` source; call `compile_resume(compilation.id)` synchronously (not `.delay`); assert `status == SUCCEEDED`, `compilation.pdf` exists, and `compilation.pdf.open("rb").read(5) == b"%PDF-"`.
- `test_compile_api_and_download`: APIClient with a token for the owning user; `POST /api/resumes/` (create from template), assert `main_tex` seeded non-empty; `POST /api/resumes/{id}/compile/` with `CELERY_TASK_ALWAYS_EAGER=True`, then `GET /api/compilations/{id}/` returns `succeeded` and a `pdf_url`; `GET /api/resumes/{id}/download/` returns 200 `application/pdf`.
- `test_unknown_template_rejected`: `POST /api/resumes/` with `template="nope"` returns 400.
- `test_owner_isolation`: a second user's `GET /api/compilations/{id}/` for the first user's compilation returns 404.

### Frontend (Next.js)

**8. Scaffold the app and wire proxying + auth.**

Create the Next.js 15 + TypeScript (App Router) app in a new `frontend/` directory at the repo root. In `frontend/next.config.mjs`, add `rewrites()` proxying `/api/:path*` and `/media/:path*` to the Django origin read from `process.env.DJANGO_URL` (default `http://localhost:8000`), so the SPA and API are same-origin and no CORS/CSRF config is needed:

```js
async rewrites() {
  const target = process.env.DJANGO_URL ?? "http://localhost:8000";
  return [
    { source: "/api/:path*", destination: `${target}/api/:path*` },
    { source: "/media/:path*", destination: `${target}/media/:path*` },
  ];
}
```

Create `frontend/lib/api.ts` exporting a `fetch`-based client that reads the token from `localStorage["betterleaf.token"]` and sets `Authorization: Token <token>` on every request; on a 401 it clears the token and redirects to `/login`.

`frontend/app/login/page.tsx`: email + password form; on submit `POST /api/auth-token/` with body `{username: email, password}`; store the returned `{token}` in `localStorage["betterleaf.token"]`; redirect to `/resumes`. (Signup/email-verification stays the scaffold's server-rendered allauth flow at `/accounts/signup/`; accounts can also be created in Django admin.)

**9. Resume dashboard.**

`frontend/app/resumes/page.tsx`: fetch `GET /api/resumes/` (list) and `GET /api/templates/`. Render the user's resumes (title, template, updated_at) linking to `/resumes/[id]`, a "Delete" per row (`DELETE /api/resumes/{id}/`), and a "New resume" button opening a modal that shows each template (`slug`, `name`), then `POST /api/resumes/` with `{title, template}` and navigate to `/resumes/[id]`.

**10. Editor page.**

`frontend/app/resumes/[id]/page.tsx`:

- Editor: CodeMirror 6 via `@uiw/react-codemirror`, with LaTeX highlighting from the `stex` legacy mode (`@codemirror/legacy-modes` + `@codemirror/language`'s `StreamLanguage`), bound to `resume.main_tex`.
- Preview: `react-pdf` (`<Document>`/`<Page>`) with the `pdfjs-dist` worker configured via `import { pdfjs } from "react-pdf"` + `pdfjs.GlobalWorkerOptions.workerSrc`. Render `latest_pdf_url` from the resume on load.
- Autosave + compile: on editor change, debounce 1000 ms; `PATCH /api/resumes/{id}/` with `main_tex`, then `POST /api/resumes/{id}/compile/` capturing the returned `{id}` as the current run. While a run is pending, poll `GET /api/compilations/{run_id}/` every 400 ms; when `succeeded`, set the preview source to that run's `pdf_url`; when `failed`, show the run's `log` in a collapsible log panel. Ignore responses whose `run_id` no longer matches the latest issued run (stale runs are dropped). Keep the last `succeeded` PDF rendered while a newer run is pending/failed, with a small "compiling…" / "stale preview" indicator.
- Toolbar: a manual "Compile" button (same compile call), and a "Download PDF" button (`<a href={`/api/resumes/${id}/download/`} download>`).
- Empty/main-tex-blank and "no PDF yet" states: show a placeholder message; the compile 400 is surfaced in the log panel.

### Domain documentation

**11. Write `CONTEXT.md` and ADRs.**

Create `CONTEXT.md` at the repo root with this glossary (single-context repo):

```md
# BetterLeaf

An AI-assisted LaTeX editor for professional resume development.

## Language

**Resume**: A user-owned LaTeX document — a `main.tex` plus a template class — that compiles to a PDF. _Avoid_: CV, document, file

**Template**: A bundled first-party LaTeX class (`.cls`) that defines a resume's layout. _Avoid_: style, theme, layout

**Compilation**: The act of running Tectonic on a Resume's `main.tex` to produce a PDF. _Avoid_: build, render, generate
```

Create `docs/adr/` with three single-paragraph ADRs:

- `0001-server-side-latex-compilation.md` — LaTeX compiles server-side via a pinned Tectonic binary in the Docker image, dispatched by Celery, not client-side WASM; chosen for full TeX package/XeTeX support and natural PDF download, at the cost of a Celery/container dependency.
- `0002-nextjs-spa-django-api.md` — the frontend is a Next.js SPA and Django serves DRF + token auth only (no server-rendered product pages); chosen for a rich editor surface, at the cost of abandoning the scaffold's server-rendered templates for the product UI.
- `0003-latex-source-of-truth.md` — raw LaTeX source (a `main.tex`, optionally styled by a template directory's `.cls`) is the source of truth, not structured/JSON resume data; AI edit and tailoring will edit LaTeX, not a data model.

## Critical files & anchors

- `config/settings/base.py` — `LOCAL_APPS` (add `betterleaf.resumes`), `REST_FRAMEWORK` (token auth already present), `MEDIA_ROOT`.
- `config/api_router.py` — register `resumes` + `compilations` viewsets and the `templates/` path.
- `compose/local/django/Dockerfile` — Tectonic install (pinned 0.16.9 + SHA-256).
- `compose/production/django/Dockerfile` — same Tectonic install in the `python-run-stage`.
- `docker-compose.local.yml` — `TECTONIC_CACHE_DIR` env + `betterleaf_local_tectonic_cache` volume on the `django` anchor (reaches `celeryworker`).

## Verification

Backend (inside the Docker Django container, which has Tectonic):

```bash
cd /home/vishesh/betterleaf
docker compose -f docker-compose.local.yml build django
docker compose -f docker-compose.local.yml up -d postgres redis django celeryworker
docker compose -f docker-compose.local.yml exec django python manage.py test betterleaf.resumes
```

Expect `test_compile_produces_pdf` and the API tests to pass (they run Tectonic for real and assert a `%PDF-` output).

Package-completeness check (answers "are all resume packages present?"): the canonical Jake's packages (`fullpage`, `titlesec`, `color`, `enumitem`, `hyperref`, `fancyhdr`, `babel`, `tabularx`) live in Tectonic's bundled package tree. Prove it, don't assume — run inside the container:

```bash
docker compose -f docker-compose.local.yml exec django \
  tectonic -X compile /dev/stdin <<'EOF' >/dev/null && echo "package-ok"
\documentclass[letterpaper,11pt]{article}
\usepackage[empty]{fullpage}\usepackage{titlesec}\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}\usepackage[hidelinks]{hyperref}\usepackage{fancyhdr}
\usepackage[english]{babel}\usepackage{tabularx}
\begin{document}ok\end{document}
EOF
```

`package-ok` on stdout proves every package resolves; a failure names the first missing package in the error. The same gate applies in `test_compile_produces_pdf`, so any future template/package addition that breaks compilation fails CI.

End-to-end (new behavior):

1. `cd /home/vishesh/betterleaf/frontend && npm install && npm run dev` (proxies `/api` and `/media` to `localhost:8000`).
2. Create a user via `docker compose -f docker-compose.local.yml exec django python manage.py createsuperuser` (or existing allauth signup), then log in at `http://localhost:3000/login` with that email + password.
3. On `/resumes`, "New resume" → pick "Jake's Resume"; the editor opens with the seeded `main.tex` and, after the initial compile, a rendered PDF preview.
4. Type a change in the editor (e.g. add `\item`) → within ~2 s the PDF preview updates to show it; the "compiling…" indicator appears and clears.
5. Click "Download PDF" → a file `{slug}.pdf` downloads and opens as a valid PDF.
6. Introduce a LaTeX error (e.g. `\invalid`) → the preview keeps the last good PDF, a stale indicator shows, and the log panel displays the Tectonic error output.

## Assumptions & contingencies

- **Tectonic network on first compile**: Tectonic downloads its TeX bundle from its server on the first compile and caches it under `TECTONIC_CACHE_DIR`. If the Celery worker has no outbound network in a target environment, this fails; fallback: pre-download the bundle into a volume on a networked machine and mount it at `/tectonic-cache` before first use.
- **Architecture**: the pinned asset/checksum are for `x86_64-unknown-linux-musl`. If a target runs `aarch64`, use the `aarch64-unknown-linux-musl` asset with SHA-256 `f9aa39017dbd51f111fdb93dda222178cbe51c8193508fc567b523cc74fff9c1` (from Oleafly's `scripts/fetch-tectonic.sh`).
- **Token storage**: the SPA stores the DRF token in `localStorage` (acceptable for slice 1; revisit httpOnly-cookie auth if XSS hardening becomes a requirement).
- **CORS**: none needed — the Next.js `rewrites` make `/api` and `/media` same-origin. If the frontend is instead deployed on a separate origin from Django, add `CORS_ALLOWED_ORIGINS` to `config/settings/local.py`/`production.py` and extend `CORS_URLS_REGEX` to also cover `^/media/.*$`.
