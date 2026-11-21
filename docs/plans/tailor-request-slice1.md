# Tailor Request: first slice

## What this slice does
The user pastes a job description. One request gives back three things at once:
- **Right panel:** a tailored resume they can download straight away.
- **Middle panel:** the coverage report (what they have, what they don't) plus the gap questions for whats missing or partially present in resume .

Answering the gap questions and updating the tailored resume and master resume from the answers comes in a later slice. So do reworded bullets the user approves, the free limit, and the page limit.


The tailored resume only picks and orders the master's own bullets. Code copies the exact words, the AI never writes any.

## The flow
1. The screen sends the job text. We save a Tailor Request and hand the work to Celery. The reply is instant.
2. Celery makes one AI call. It returns the requirements, how well each is covered, the gap questions, and which master items go on the resume and in what order.
3. Code checks the answer, builds the resume from the master's own text, saves it as a normal Resume, and marks the request ready.
4. The screen polls one URL until it's ready, then shows the report and the resume.

## What the response looks like

Start: `POST /api/tailor-requests/` with `{"job_text": "..."}` → 202
```json
{ "id": "7c1e…", "status": "analysing" }
```

Poll: `GET /api/tailor-requests/7c1e…/` when ready:
```json
{
  "id": "7c1e…",
  "status": "ready",
  "resume_id": "a91f…",
  "scores": {
    "must_have":    { "earned": 2.5, "total": 4 },
    "nice_to_have": { "earned": 0,   "total": 1 }
  },
  "requirements": [
    { "id": "req_1", "text": "Python", "importance": "must_have", "priority": 1,
      "status": "met",
      "evidence": [{ "source_id": "9f3e1ac2b4d0", "quote": "Built REST APIs in Python" }],
      "rationale": "Direct production use at Acme." },
    { "id": "req_3", "text": "Kubernetes", "importance": "must_have", "priority": 2,
      "status": "not_met", "evidence": [], "rationale": "No mention anywhere." }
  ],
  "gap_questions": [
    { "requirement_id": "req_3", "question": "Have you deployed services on Kubernetes, even in side projects?" }
  ]
}
```
- `resume_id` is a normal Resume. The screen loads and downloads it with the calls that already exist (`/api/resumes/{id}/`, `compile`, `download`).
- While working: `status` is `analysing` and nothing else is filled in.
- If it breaks: `{"status": "failed", "error": "…"}`.
- Start returns 400 for empty text or when the user has no master resume yet.

## Models touched
- **New `TailorRequest`** (`models.py`, migration 0007):
  - `id`, `workspace` (FK), `master_resume` (FK), `job_text`
  - `status`: `analysing`, `ready` or `failed`
  - `result` (JSON): the checked AI answer, requirements, matches and gap questions only
  - `resume` (OneToOne to Resume, empty until built, SET_NULL)
  - `counted` (set when it succeeds, ready for the free limit later; nothing enforces it yet)
  - `error`, `created_at`, `updated_at`
- **Master resume**: its data now carries ids (your unstaged `schemas.py` change: bullets are `{id, text}` and every item has an `id`). New uploads get them automatically. Old masters get them once, saved back when their first tailor request starts, so ids stay stable.
- **Resume**: no change. The tailored resume is a new Resume row, template `jakes`, linked to the master.
- Your unstaged `latex.py` change (`bullet['text']`) is part of this and stays.

## Services (`betterleaf/resumes/services/`)
- `llm.py`: one function `call_llm_json(system, user, max_tokens)`. It's the DeepSeek call from `parser.py`, moved out, and `parser.py` switches to it.
- `tailor/schemas.py`: your reference models, with these changes:
  - `TailoredResume` becomes a plain **selection**: experiences, projects and achievements as an id plus an ordered list of bullet ids, education ids, and skill groups as a group id plus the skill words to keep. There is no `text` and no `summary`.
  - `Requirement` gets a `priority` number (1 = most important).
  - The checks stay: every requirement matched once, evidence needs real ids, and no unknown ids.
  - New checks: each evidence `quote` must appear in the line it names, each bullet id must belong to the item it's listed under, and each kept skill word must exist in that group.
- `tailor/master_view.py`:
  - `ensure_ids(master)`: the one-time backfill for old masters.
  - `master_to_prompt(data)`: the master as numbered plain text, e.g. `[exp:ab12] Senda, AI Systems Engineer Intern` then `  [b:9f3e] Built REST APIs…`.
  - `master_ids(data)`: every valid id, for the checks above.
- `tailor/analyse.py` → `run_tailoring(job_text, master_data)`: calls the AI, checks the answer, and on a check failure asks once more, then gives up. Afterwards code cleans up the gap questions: keep only `not_met` ones, drop any for met or partial requirements, and sort must-haves first, then by `priority`.
- `tailor/assemble.py` → `build_resume_data(master_data, selection)`: builds the resume's data from the master's own items in the AI's order. It keeps the master's section order and includes the summary only if the master has one. Then `render_resume(...)` makes the LaTeX.
- `tailor/scores.py` → `score(requirements)`: met = 1, partial = 0.5, not met = 0, added up separately for must-have and nice-to-have.

## Prompt (`betterleaf/resumes/prompts/tailor.md`)
One plain text file loaded by `analyse.py`. It tells the AI to:
1. List the job's requirements, each must-have or nice-to-have (must-have if unclear), with a priority.
2. For each, find evidence by master id, fill evidence first, then pick met, partial or not met. Partial means only adjacent evidence, for example a project when the job wants work experience.
3. Write one short question for each requirement that isn't met.
4. Pick which master items go on a one-page resume and in what order (hint: about 4 bullets per role, up to 3 projects). Use ids only and never write new text.
Never invent anything.

## Celery (`tasks.py`)
One task, `analyse_job(request_id)`:
- Runs `ensure_ids`, then `run_tailoring`, then `build_resume_data`, then creates the Resume, then saves the result and sets `ready` and `counted`.
- Any failure sets `failed` with a plain message and leaves `counted` off.
- Retries only on network trouble, at most 2 times.
- `soft_time_limit=120`, because the global 60 seconds is too short for a call that big.

## API (`views.py`, `serializers.py`, `config/api_router.py`)
- `TailorRequestViewSet` with only create and retrieve, using `HasWorkspace` and showing only the caller's own requests.
- `create` rejects empty text and a missing master, saves the row, and queues `analyse_job`.
- The serializer joins requirements with their matches and computes `scores` on read.
- Register `tailor-requests` in `config/api_router.py`.

## Order of work
1. `TailorRequest` model and migration.
2. `llm.py` (and switch `parser.py` to it).
3. `tailor/schemas.py`, `master_view.py`, `scores.py`.
4. The prompt, then `analyse.py` and `assemble.py`.
5. The Celery task.
6. Serializer, viewset, route.

## How to check it works
- Master with Python and no Kubernetes: Python is met, Kubernetes is not met with a question, and the scores add up.
- The tailored resume's bullets are all word-for-word master bullets.
- The download works through the existing compile and download calls.
- Gibberish text: `failed`. A user with no master: 400. Someone else's request id: 404.
- An old master (no ids): works, and the ids are saved afterwards.

## Later slices
Gap answers and the resume update, user-approved bullet variants, the free limit, the page limit.
