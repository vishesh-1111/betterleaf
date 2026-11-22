# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Any job seeker, from freshers and graduates to experienced professionals, who is tired of moving between ChatGPT and Overleaf and wants to apply to jobs quickly. Job: turn one resume into many JD-tailored resumes with almost no back-and-forth.

## Product Purpose

BetterLeaf is an AI-assisted LaTeX resume workspace. The user uploads a resume once; it is parsed into a master resume (source of truth). Pasting a job description produces a coverage report, optional gap questions, and a tailored resume version with live-compiled preview and PDF download. Success: a tailored, download-ready resume in minutes, without the user's facts being altered or invented.

## Positioning

The AI selects, orders and tags what the user already has; it does not rewrite or invent. Every skill needs evidence (company, project, achievement or certification). A neighboring product that rewrites bullets freely could not truthfully claim this.

## Operating Context

- Flow: upload resume (PDF) → parsed into master → editor with LaTeX source and compiled PDF preview → paste JD → coverage report → inline gap questions → master update proposals (approve/reject) → tailored version → edit/download.
- Masters feed tailored resumes; tailored versions are snapshots and never flow back into the master.
- Editing LaTeX directly detaches a resume from the AI.
- Real sample resumes live in `Real_Resumes/`.

## Capabilities and Constraints

- v1: start from resume upload only; JD as pasted text; one template (Jake's resume); PDF download; LaTeX editor; free tier with a cap on tailor requests.
- Live LaTeX compile, PDF download, AI edit, JD tailor, resume upload → extract → LaTeX are the current features (`ProductSummary.txt`).
- Coverage report states: Matched, Needs input (must-have, no evidence), Not mentioned. Requirements are must-have or good-to-have; project-only evidence for professional-experience requirements earns partial credit.
- Gap questions are inline cards on one scrollable page: no modals, all skippable, generate possible at any time.
- Stack (existing): Django + Celery backend (`betterleaf/`), Next.js frontend in `frontend/apps/web` (derived from open-prism / assistant-ui), LaTeX compile server in `compose/local/latex-server`.
- Later, not v1: direct master editing, starting without a resume, URL/file JD input, more templates, "make this stronger" rewording.
- Undecided: behavior at the free cap; unparseable uploads; re-upload wording conflicts; partial-match scoring beyond project-only; user correction of must/good-to-have; one-page limit; whether the coverage report is kept per version (see `BetterLeaf Core User Behaviours.md`).

## Brand Commitments

Name: BetterLeaf. No other voice, asset, or identity commitments confirmed yet.

## Evidence on Hand

- Product behavior spec: `BetterLeaf Core User Behaviours.md`; summary: `ProductSummary.txt`.
- Sample resumes: `Real_Resumes/` (11 PDFs).
- No testimonials, customers, benchmarks, pricing, or usage data exist; future work must not fabricate them.

## Product Principles

- The master resume is the source of truth.
- The AI selects, orders and tags; it does not rewrite unless the user asks (exception: a bullet drafted from a gap answer, user-approved).
- Every skill needs evidence; if an answer is too thin, add nothing.
- Minimum friction: one page, inline questions, skip anything, generate anytime.
- Versions are snapshots; edits never flow back to the master.

## Accessibility & Inclusion

No product-specific standard established yet.
