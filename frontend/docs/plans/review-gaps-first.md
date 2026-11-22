# Review screen: gaps first

Status: planned, not built.

## The idea
Right now the screen shows a lot: the score, then three lists (Matched, Needs input, Not mentioned), and the questions way down at the bottom. Most people only need to do one thing here: **fill in the gaps**. So the screen should lead with that.

## What the user will see, top to bottom
1. **How well you match** – the two scores, as now (Must-have 10.5 of 13, Nice-to-have 2 of 5).
2. **One card per gap**, must-haves first, then nice-to-haves. Each card has:
   - a small tag: **Must-have** or **Good to have**
   - what the job asks for
   - a box to type your answer ("A sentence or two is enough. Leave empty to skip.")
   - a small "Where was this?" dropdown under the box, already filled in with the first job. It stays because the app needs to know which job or project the new bullet belongs to.
3. **Draft bullets** button under the cards.
4. **"See what already matched"** – a closed, folded line at the very bottom. Open it to see the matched items with the quotes from your resume. Nobody has to scroll past it.

## After "Draft bullets"
The cards give way to the suggested bullets (accept, edit or reject, then Confirm). The scores stay on top. A small "Edit my answers" link goes back to the cards.

## What goes away
- The separate "Matched", "Needs input" and "Not mentioned" lists.
- The "Questions for you" section sitting below them (its cards move up and absorb the requirement text and tag).
- The "Partly covered" label, since those are no longer shown by default (they appear only inside the folded matched section).

## What does not change
- Which gaps get a card: only requirements with nothing on the resume, same as today. Nothing changes on the server.
- Scores, job bar, running and error states, and the Confirm step.

## Steps
1. Reshape the question cards: add the Must-have / Good to have tag, tidy the wording.
2. Reorder the screen: scores, then cards, then Draft bullets, then the folded "matched" section.
3. Swap cards for suggestions after drafting, plus the "Edit my answers" link.
4. Remove the old three lists.
5. Check it: a job with several gaps, a job with no gaps (show a short "Nothing missing" note), a phone-width screen, and one full run through Confirm.
