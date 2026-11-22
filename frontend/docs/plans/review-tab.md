# Review tab (middle pane)

Status: planned, not built.

## What this adds
A third tab, **Review**, next to Edit and LaTeX. It is where a user pastes a job description, watches the tailoring run, reads the coverage report, answers gap questions and approves new bullets. The backend for all of this already exists (slices 1 and 2). The frontend has none of it yet.

The left list and right PDF stay as they are.

## What the user sees
One scrolling column, no modals, everything skippable.

1. **Nothing running:** a big text box, "Paste a job description", with a **Tailor** button and a "Paste from clipboard" button. The box is focused when the tab opens.
2. **Running:** the box shrinks to one line, "Job: first line of the text · Change", and a short "Analysing the job…" state shows below it.
3. **Ready:** cards, top to bottom:
   - **Scores:** Must-have 2.5 of 4, Nice-to-have 0 of 1.
   - **Requirements:** grouped as Matched, Needs input (must-have, no evidence) and Not mentioned. Each one shows its evidence quote and a one-line reason.
   - **Gap questions:** one card per question. The user picks where it happened (a job, project or achievement), picks which one, and types a short answer. Skip any. One **Draft bullets** button sends all answers together.
   - **Drafting:** "Writing bullets from your answers…"
   - **Proposals:** each shows the new bullet, which job or project it goes under, and an optional skill word. The user can accept, edit or reject. A sticky **Confirm** button sends the accepted ones.
4. **After Confirm:** the master is updated and a new tailored resume starts. The screen moves to the new job, and its report replaces the old one. The old resume stays in the left list.

The yellow highlight stays reserved for AI changes.

## Which resumes get the tab
- **A tailored resume:** Review shows that job's report.
- **The original resume:** Review shows the paste box, or the running job if one is in progress.
- **A resume with no master (for example, never uploaded):** a short "Upload a resume first" message and the existing upload button.

## How the screen talks to the server
- **Start:** `POST tailor-requests/` with the job text. It replies at once.
- **Waiting:** poll `GET tailor-requests/{id}/` about every 2 seconds. Stop when the status is `ready` or `failed`. Slow down after 30 seconds and stop after 3 minutes with a "Taking too long, try again" message.
- **Answers:** `POST tailor-requests/{id}/answers/`. Status goes to `drafting`, and the screen keeps polling until it returns to `ready` with proposals.
- **Confirm:** `POST tailor-requests/{id}/confirm/` returns a new request id. Poll that one. When it is ready, load its resume (`GET resumes/{resume_id}/`) and add it to the left list like any other resume, then compile it for the PDF.
- All of this goes into `lib/api.ts` (new functions and types) and a small `use-tailor-request` hook. The tailor state lives in the existing store next to the files, so the tab and the left list stay in sync.

## Staying in sync
- **Tabs:** the tab bar's status label also shows "Analysing job…" and "Drafting bullets…" while a job runs.
- **PDF:** a finished tailored resume goes through the same compile path the form uses, so the right pane updates by itself.
- **Reload mid-job:** the job lives in the database, so the screen resumes polling after a reload (see the backend change below).
- **Double clicks:** the buttons are disabled while a request is in flight. The server adds no locks.

## Edge cases
- **Empty text:** Tailor stays disabled.
- **Failed job:** shows the server's message and a **Try again** button, and the pasted text is kept.
- **Drafting fails:** the server puts the request back to `ready` with an error. Show the error, keep the answers on screen and let the user submit again.
- **Nothing accepted:** Confirm does nothing, so the button stays disabled until at least one bullet is accepted.
- **Edits unsaved when leaving the tab:** answers and edited bullets are kept in memory, so switching tabs doesn't lose them.
- **Master has no items of a kind** (for example, no projects): that choice is hidden in the picker.

## Small backend change
The screen can't work with the server as it is, because it needs three things the API doesn't return yet:
1. **Where answers can go:** a list of the master's jobs, projects and achievements, each with an id and a readable label. Put it on the tailor request response as `answer_targets`, so the picker needs no extra call. Skill groups aren't listed because the server picks those.
2. **Finding the job after a reload:**
   - **Tailored resume:** its data includes `tailor_request_id`.
   - **Workspace payload:** includes `active_tailor_request_id`, the newest request that is `analysing` or `drafting`. A running job has no resume yet, so the original resume's Review tab needs this one.
3. **Proposal labels:** each proposal already carries its item id. The screen looks the label up in `answer_targets`.

Each gets a small test.

## Build order
1. **Backend:** the three additions above, with tests.
2. **API client:** types and calls in `lib/api.ts`, plus the polling hook. Check by running a job from the browser console.
3. **Tab:** add Review to `middle-pane.tsx` (keyboard arrows cover three tabs), with the paste box and running state.
4. **Report:** scores and requirement cards.
5. **Gap questions:** the answer cards and Draft bullets.
6. **Proposals:** accept, edit, reject and Confirm, then switching to the new resume.
7. **Polish:** error and timeout states, reload resume, a check on desktop and phone.

## How to check it works
- Paste a job, then see Analysing, then a report. The scores match the API.
- Answer one gap, skip the rest, edit a drafted bullet, confirm. The new resume appears in the left list, compiles, and its report doesn't ask the answered question again.
- Reload while analysing and while drafting. The screen picks up where it was.
- Bad input, a failed job and a slow job each show the right message.
- Someone else's request id returns 404 and the screen shows an error, not a blank.
