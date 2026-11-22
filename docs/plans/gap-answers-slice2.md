# Gap Answers: second slice

## What this slice does
After the report, the user answers the gap questions (all at once, skipping any they like). The AI turns each answer into a resume bullet written for this job. The user checks the bullets. Once confirmed, the master resume is updated and the tailoring runs again.

## The flow
1. The user sees the gap questions. For each one they pick where the experience came from (a job, a project or an achievement), pick which one, and write a short description. Skipped questions are simply left out.
2. One AI call turns all the answers into proposals. Each proposal is one of:
   - a new bullet, plus optionally a skill word and the skill group it belongs to
   - "no change", with a reason, when the answer is too thin
3. The screen waits for the proposals, same as it waits for the first report.
4. The user accepts, rejects or edits each proposal. What they leave on screen is what gets saved. The AI never changes it after that.
5. The user presses confirm. The bullets go into the master and a new tailor request starts.
6. The new request shows its own report and resume. The old one stays as it was.

## Rules
- **Only add.** Proposals add a new bullet to an existing job, project or achievement. No editing old bullets, no creating new jobs or projects. A source type with nothing in the master is hidden.
- **Nothing invented.** The AI may only use facts from the user's answer, and must not add numbers or claims they didn't give.
- **Skills need a bullet.** A skill word is only added alongside its bullet, into an existing skill group. Never a new group.
- **No repeat questions.** The new request is told what the user answered and skipped, so it doesn't ask the same gaps again. It isn't told the master changed.
- **Old requests stay.** Each re-run is a new request and a new resume. The old ones are never overwritten.
- **Free limit.** Only the first request for a job counts. Follow-ups are free.
- **Double clicks.** The screen prevents them. The server adds no extra locks.

## Tell first and follow-up requests apart
Each request gets two new fields:
- `parent`: empty for the first request, otherwise the request it came from.
- `kind`: `initial` or `gap_followup`. Later we can add `instruction` for "change this point" with no job description.

A follow-up copies the job text from its parent, so the user never pastes it again.

## Change to slice 1: skills section
- At most 10 skills per skill group (Languages, Frameworks, and so on).
- Skills that match the most important job requirements and appear in the chosen bullets come first. Other skills follow.
- The AI orders them. Code cuts the list at 10.

## What changes
- **TailorRequest:** add `parent`, `kind`, `proposals`, and the answers (migration 0008).
- **Prompt:** new `prompts/gap_answers.md` for the answers-to-bullets call. The tailor prompt gets the skills rule and the prior answers and skips.
- **Services:** new `tailor/gap_answers.py` for the AI call and checks. A small function that writes accepted proposals into the master.
- **Celery:** new task for the answers call. `analyse_job` handles follow-ups and sets `counted` only for `initial`.
- **API:**
  - `POST /api/tailor-requests/{id}/answers/` saves answers, queues the AI call, returns 202.
  - `POST /api/tailor-requests/{id}/confirm/` saves accepted bullets, creates the follow-up request, returns 202 with its id.
  - The existing GET also returns the proposals.

## How to check it works
- Answer one gap for a job: get a bullet written from only that answer, attached to the chosen item.
- Skip every gap: nothing changes.
- Edit a proposal before confirming: the master gets the edited text, word for word.
- Confirm: the master has the new bullet and skill word, and a new request starts with the same job text and `kind=gap_followup`.
- The new report doesn't ask the questions the user already answered or skipped.
- The old request and its resume are unchanged. The new one doesn't count toward the limit.
- A skill group never goes past 10 skills on the tailored resume.

## Build plan

### Models
Only one model is touched: **TailorRequest** (migration 0008). No new tables. New fields:
- `parent`: the request this one came from. Empty for the first request.
- `kind`: `initial` or `gap_followup`.
- `answers`: what the user typed for each gap.
- `proposals`: the bullets the AI drafted from those answers.
- `handled_gaps`: a running list of gaps already answered or skipped, by requirement text. Each follow-up copies its parent's list and adds the latest round. This is what keeps old questions from coming back.
- New status `drafting`: the AI is writing bullets. When done, the request goes back to `ready`. If the AI call fails, it also goes back to `ready`, with an error message, and the user can submit again.

The **master resume** is changed by the confirm step (new bullets, new skill words), but its shape stays the same. **Resume** is unchanged.

### Small services (`betterleaf/resumes/services/tailor/`)
- `gap_answers.py`: sends the job, the requirements and the user's answers to the AI and gets proposals back. Code then checks that the item and skill group it named really exist, and tries once more if not. Same pattern as `analyse.py`.
- `master_update.py`: takes the accepted proposals and writes them into the master: add the bullet with a fresh id, add the skill word to its group if missing. Nothing else is touched.
- `analyse.py` (small edits): add `handled_gaps` to the AI message, and cut each skill group to 10.
- `scores.py`, `assemble.py`: no change.
- Prompts: new `prompts/gap_answers.md`. `prompts/tailor.md` gets the "skip handled gaps" line and the skills rule.

### Celery (`tasks.py`)
- New `draft_proposals(request_id)`: runs `gap_answers`, saves proposals, sets status back to `ready`. Same retry and time limit rules as `analyse_job`.
- `analyse_job` changes: a follow-up request works the same way, but `counted` is only set for `initial`.

### Views (`views.py`, `serializers.py`)
Two extra actions on the existing tailor request view:
- `POST /api/tailor-requests/{id}/answers/`: checks the request is `ready`, saves the answers, sets `drafting`, queues `draft_proposals`, returns 202.
- `POST /api/tailor-requests/{id}/confirm/`: takes the accepted proposals with their final text. In one step it updates the master, creates the follow-up request (job text copied, `parent` set, `handled_gaps` filled in), queues `analyse_job` and returns 202 with the new id. If nothing was accepted, it does nothing.

The existing GET also returns `kind`, `parent_id` and `proposals`.

### Order of work
1. Model fields and migration 0008.
2. `master_update.py`, with tests.
3. `gap_answers.py` and its prompt, with tests.
4. Tailor prompt edits, skills cap, `handled_gaps` in `analyse.py`.
5. The two Celery changes.
6. Serializer and the two views.
7. Run the checks above through the API.

## Later
"Change this point" with no job description, editing old bullets, creating new jobs or projects from an answer, the free limit, the page limit.
