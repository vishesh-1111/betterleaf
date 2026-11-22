# Resume Editor (middle pane)

Status: planned, not built.

## What this adds
The middle pane of the workspace gets three tabs:

- **Edit** (opens first): a form to change your resume: name, contact details, jobs, projects, skills and so on.
- **LaTeX**: the code editor you already have.
- **Review**: the coverage report and gap questions. Built later, after Edit.

The left list and the right PDF stay as they are.

## How it works
1. You type in the form.
2. About half a second after you stop, your changes are saved.
3. The LaTeX updates by itself to match.
4. The PDF rebuilds by itself, so you always see the latest version.

A small label in the tab bar shows what's happening: Saved, Saving, Building PDF, or Couldn't save.

## What you can change
- Every field: text, dates, links.
- Add, remove and drag to reorder bullets, jobs, projects, education and skill groups.
- Reorder whole sections, and turn the summary on or off.
- Skills appear as small tags you can add and remove.
- Deleting something shows an Undo.

## Look
Same feel as the rest of the workspace: dark green text, pale background, white cards. One scrolling column: your name and contact details first, then a card for each section in resume order. Long resumes can be folded up. The yellow highlight stays reserved for AI changes.

## Edge cases
- **Resume with no form data** (for example one that wasn't uploaded): shows a short message and an "Upload a resume" button. The LaTeX tab still works.
- **Save fails:** your typing stays on screen, with a Retry button.
- **Typing fast:** only the latest change gets saved and built.

## Known gap
If you edit the LaTeX by hand and then change something in the form, the LaTeX is rebuilt and your hand edits are lost. We're leaving this for later.

## Behind the scenes
- The server turns the form data into LaTeX, so there is one source of truth.
- Needs a small backend change (accept the form data on save) and a drag-and-drop library, which I'll ask about before adding.

## Build order
1. Backend: accept and save the form data, with tests.
2. Tabs in the middle pane, with the LaTeX editor moved under one.
3. The form: name and contact, then sections and bullets.
4. Auto-save and auto-build PDF.
5. Add, remove, drag to reorder, skill tags.
6. Empty, error and loading states, then a check on desktop and phone.
