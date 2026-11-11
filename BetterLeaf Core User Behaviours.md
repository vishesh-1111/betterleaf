# BetterLeaf: Core User Behaviours

Nov 4, 2026 · @Vishesh Kumar Gautam

BetterLeaf lets a job seeker upload a resume once, then turn any job description into a tailored resume with almost no back-and-forth. The master resume is the source of truth, and the AI selects and orders what the user already has instead of inventing anything.

## Principles

Every behaviour below follows these rules.

- **The master resume is the source of truth.** A tailored resume is always built from it, never from the previous tailored resume.
- **The AI selects, orders and tags. It does not rewrite.** The user's own words stay unless the user asks for a change. The one exception is a bullet drafted from a gap answer, which the user approves first.
- **Every skill needs evidence.** Evidence is a company, a project, or an achievement or certification. There is no "currently learning" or "general knowledge" skill.
- **Nothing is invented.** If the user's answer is too thin to support a claim, nothing is added.
- **Minimum friction.** One scrollable page, no modals, questions shown inline, and the user can skip everything and generate at any time.
- **Versions are snapshots.** Later master changes do not alter old tailored resumes, and edits to a tailored resume never flow back into the master.

## Who it is for and what v1 covers

**Users.** Any job seeker, from freshers and graduates to experienced professionals, who is tired of moving between ChatGPT and Overleaf and wants to apply to jobs quickly.

**v1 scope**

- Start from a resume upload (no other way to begin yet)
- Job description given as pasted text
- One resume template (Jake's resume), with PDF download
- LaTeX editor available, which detaches that resume from the AI
- Free tier with a cap on tailor requests

## Behaviours at a glance

| # | Behaviour | What the user does | What happens | v1 |
| --- | --- | --- | --- | --- |
| 1 | Upload first resume | Uploads a file | Parsed into the master and opened in the editor | Yes |
| 2 | Request a tailor | Pastes a JD | Coverage report appears | Yes |
| 3 | Answer a gap question | Picks where the experience came from and describes it | AI proposes a master update | Yes |
| 4 | Skip questions | Taps generate without answering | Resume is built from what the master already has | Yes |
| 5 | Approve master updates | Accepts or rejects each proposed change | Approved changes are saved to the master | Yes |
| 6 | Get the tailored resume | Waits for generation | New version with preview | Yes |
| 7 | Edit a tailored resume | Changes text or order | Change stays in that version only | Yes |
| 8 | Edit LaTeX | Opens the LaTeX editor | Resume is detached from the AI | Yes |
| 9 | Download | Downloads the PDF | PDF of the chosen version | Yes |
| 10 | Re-upload a resume | Uploads a newer or older file | Review list of only what is new, then merged | Yes |
| 11 | Hit the free cap | Requests another tailor | Not defined yet | Yes |
| 12 | Edit the master directly | Adds, edits, deletes items | Master changes | Later |
| 13 | Start without a resume | Fills a guided form | First master is built | Later |
| 14 | Other JD inputs | Pastes a URL or uploads a file | JD is read | Later |

## First upload: how the master resume is created

The user uploads their resume and lands straight in the editor with it already parsed. There is no review screen.

**What the master holds after parsing**

- Contact details and, if the resume has one, a summary
- Experiences: jobs, education, certifications
- Projects, with links where the resume gave them
- Achievements
- Skills, each remembering where it came from (the skills list, or a specific bullet)

**Example.** Priya uploads a PDF with one job at Acme, two projects, a degree and a skills line. She sees her resume in the editor within seconds. Behind it, the master now holds one job with its bullets, two projects with their bullets, one education entry and her skills.

**Why no review screen.** It keeps the first minute free of friction. Mistakes in parsing are fixed later, when the user edits the resume or the master.

## Tailor request: the end-to-end flow

A tailor request always starts from the master resume.

1. The user pastes the job description.
2. The system reads it and lists the requirements, marking each as must-have or good-to-have.
3. It compares each requirement against the master and finds the evidence.
4. The coverage report is shown on one page.
5. For each missing must-have, an inline question card asks the user for context. This step is optional.
6. From the answers, the AI proposes updates to the master. The user approves or rejects each one.
7. Approved updates are saved to the master.
8. The tailored resume is generated from the updated master: it picks and orders experiences, bullets, projects and skills for this JD. A summary is included only if the user's master has one.
9. The new version is saved, and the user sees the preview, can edit it, and can download the PDF.

**Skipping.** The user can jump from the report straight to step 8 at any time. Unanswered questions simply mean those requirements stay uncovered.

**Free cap.** Each request counts against the free tier's cap on tailor requests.

## The coverage report

The report opens with a count, then lists every requirement in one of three states.

**Overview.** Must-have: 8/10 covered. Good-to-have: 3/5 covered.

**The three states**

- **Matched.** Evidence exists in the master. Shown with a short snippet and where it came from (company or project).
- **Needs input.** A must-have with no sufficient evidence. The user may have the experience but never wrote it down.
- **Not mentioned.** A must or a good-to-have that was not found. Shown, but never asked about.

**Partial match.** When the JD asks for professional experience and the only evidence is a project, the requirement counts is reduced accordingly.

**Illustrative example** (JD: Backend Engineer)

| Requirement | Level | State | Evidence shown |
| --- | --- | --- | --- |
| Python | Must | Matched | "Built REST APIs in Python serving 2M requests/day" (Acme) |
| PostgreSQL | Must | Matched | Skills line and the Inventory project |
| Terraform | Must | Partial, half credit | Personal project only; the JD asks for professional use |
| Kubernetes | Must | Needs input | None found |
| Kafka | Good-to-have | Not mentioned | None found |

Must-have score here: 2.2 of 4. Good-to-have: 0 of 1.

## Missing must-haves: the inline question card

Each uncovered must-have gets a card directly on the page. It is not behind a button or a modal.

**The questions**

1. **Where did you gain this experience?** Professional experience, Project, or Achievement / Certification.
2. A follow-up that depends on the answer(automatically updates on the selection of where did you gain this experience :
   - Professional experience: which company? (existing companies, plus Other)
   - Project: which project? (existing projects, plus Other)
   - Achievement / Certification: what is its title?
3. **What did you do?** A small text area for context.

There is no "currently learning" or "general knowledge" option, because every skill needs evidence.

**Worked example.** The JD requires Kubernetes, and the master never mentions it.

1. Where? Professional experience.
2. Which company? Senda.
3. What did you do? "Used Kubernetes to deploy containerized Django applications."

**What the AI proposes.** After the answer, the AI decides the right update and shows it as a before and after:

- Add the skill to the Skills section
- Add or modify a bullet on the experience (here, a Senda bullet such as "Deployed containerized Django applications on Kubernetes")
- Add or modify a bullet on a project
- Add an achievement or certification
- Make no change if the answer is too thin to support a claim

The user approves or rejects each proposal. Approved updates go into the master, and the tailored resume is then generated from it.

**Good-to-haves.** Shown in a compact list, covered and uncovered. No questions are asked for them.

**Skipping.** Every card can be skipped, and the resume can be generated at any time.

## After tailoring: editing, LaTeX, versions, download

- **Preview and download.** The user sees the resume in the single Jake's resume template and can download it as a PDF.
- **Editing a tailored resume.** The user can reword or remove text in that version. The change stays in that version and never flows back to the master.
- **LaTeX editor.** Available, with a warning first: editing the LaTeX detaches that resume from the AI, so tailoring will no longer update it.
- **Versions.** Every tailor request creates a version. Versions are snapshots: adding experience to the master later does not change them.
- **Free tier.** Tailor requests are capped. What the user sees at the cap is still to be decided (see open questions).

## Re-uploading a resume

A user who already has a master can upload another resume: a newer one, or an older version with bullets they dropped.

1. The system parses the new file and compares it with the master.
2. Only what is new is shown, as a review list: new roles, bullets, projects, skills.
3. The user approves or rejects each item.
4. Approved items are merged into the master. Duplicates are skipped.

**Example.** Priya uploads her updated resume. The review list shows one new job at Beta Corp with three bullets, one new bullet under Acme, and two new skills. She approves everything except one skill, and the master grows accordingly.

Existing tailored resumes are not changed.

## Later, not in v1

- Editing the master directly (add, edit, delete experiences, bullets, skills), planned as the last piece
- Starting without a resume, for example through a guided form
- Other ways to give a JD: URL, file upload, browser extension
- More templates and style controls
- Rewording on request (a "make this stronger" action)

## Open questions

- [ ] What does the user see at the free cap: blocked, an upgrade prompt, or a reset after a period? What counts as one request?
- [ ] What happens if the uploaded file cannot be parsed (scanned PDF, odd layout)?
- [ ] On re-upload, what if the same job appears with different wording? Keep the old, take the new, or ask?
- [ ] Half credit is set for project-only evidence. How are years ("3+ years") and other partial matches scored?
- [ ] Must-have versus good-to-have comes from the JD wording. Can the user correct it?
- [ ] If the user tailors again after detaching to LaTeX, does that create a new version and leave the detached one alone?
- [ ] What if the pasted text is not a real JD, or has no clear must-haves?
- [ ] Is the coverage report kept on each version so the user can reopen it later?
- [ ] Is the tailored resume limited to one page, and who decides what gets dropped?
- [ ] If the user's gap answer is too thin to support a claim, what does the card tell them?
