import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * The Review tab against a mocked API: paste a job, read the report, answer a
 * gap, approve the drafted bullet, and land on the follow-up resume. No real
 * backend or LLM is needed, so this runs anywhere the Next dev server does.
 */

const API = "http://localhost:8000";
const CORS = {
  "Access-Control-Allow-Origin": "http://localhost:3000",
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Allow-Headers": "content-type,x-csrftoken",
  "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
};

const ITEM = "exp1";
const TARGETS = [
  { source_type: "experience", item_id: ITEM, label: "Acme, Engineer (2020)" },
];

function resume(id: string, title: string, tailorRequestId: string | null) {
  return {
    id,
    title,
    slug: id,
    template: "jakes",
    main_tex: "\\documentclass{article}\\begin{document}Hi\\end{document}",
    structured_data: { name: "Jane Doe" },
    tailor_request_id: tailorRequestId,
    updated_at: "2026-01-01T00:00:00Z",
  };
}

const report = (id: string, resumeId: string) => ({
  id,
  status: "ready",
  kind: id === "t1" ? "initial" : "gap_followup",
  job_text: "Backend engineer\nWe use Kubernetes",
  parent_id: null,
  resume_id: resumeId,
  scores: {
    must_have: { earned: 1, total: 2 },
    nice_to_have: { earned: 0, total: 0 },
  },
  requirements: [
    {
      id: "req_1",
      text: "Python",
      importance: "must_have",
      priority: 1,
      status: "met",
      evidence: [{ source_id: "b1", quote: "Built REST APIs in Python" }],
      rationale: "Direct production use.",
    },
    {
      id: "req_2",
      text: "Kubernetes",
      importance: "must_have",
      priority: 2,
      status: "not_met",
      evidence: [],
      rationale: "No mention.",
    },
  ],
  gap_questions:
    id === "t1"
      ? [{ requirement_id: "req_2", question: "Have you used Kubernetes?" }]
      : [],
  answer_targets: TARGETS,
  proposals: [],
});

async function mockApi(page: Page) {
  const polls: Record<string, number> = {};
  let answered = false;

  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({
      status,
      contentType: "application/json",
      headers: CORS,
      body: JSON.stringify(body),
    });

  await page.route(`${API}/api/**`, async (route) => {
    const req = route.request();
    const { pathname } = new URL(req.url());
    const path = pathname.replace("/api/", "");
    if (req.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: CORS });
    }

    if (path === "workspace/") {
      return json(route, {
        workspace_id: "w1",
        anonymous: true,
        resumes: [resume("r1", "Jane", null)],
        active_tailor_request_id: null,
      });
    }
    if (path === "tailor-requests/" && req.method() === "POST") {
      return json(route, { id: "t1", status: "analysing" }, 202);
    }
    if (path === "tailor-requests/t1/answers/") {
      answered = true;
      polls.t1 = 0;
      return json(route, { id: "t1", status: "drafting" }, 202);
    }
    if (path === "tailor-requests/t1/confirm/") {
      return json(route, { id: "t2", status: "analysing" }, 202);
    }
    if (path === "tailor-requests/t1/") {
      polls.t1 = (polls.t1 ?? 0) + 1;
      if (!answered) {
        // First poll: still working. Then the report.
        return json(
          route,
          polls.t1 === 1
            ? {
                id: "t1",
                status: "analysing",
                kind: "initial",
                job_text: "Backend engineer\nWe use Kubernetes",
                parent_id: null,
              }
            : report("t1", "r2"),
        );
      }
      return json(route, {
        ...report("t1", "r2"),
        status: polls.t1 === 1 ? "drafting" : "ready",
        proposals:
          polls.t1 === 1
            ? []
            : [
                {
                  id: "p1",
                  requirement_id: "req_2",
                  requirement_text: "Kubernetes",
                  source_type: "experience",
                  item_id: ITEM,
                  change: "add_bullet",
                  bullet: "Deployed Django services on Kubernetes",
                  skill: "Kubernetes",
                  skill_group_id: "g1",
                  reason: "",
                },
              ],
      });
    }
    if (path === "tailor-requests/t2/") {
      return json(route, report("t2", "r3"));
    }
    if (path === "resumes/r2/")
      return json(route, resume("r2", "First tailored", "t1"));
    if (path === "resumes/r3/")
      return json(route, resume("r3", "Second tailored", "t2"));
    if (path.endsWith("/compile/")) {
      return json(
        route,
        { id: "c1", status: "failed", pdf_base64: "", log: "! mocked" },
        201,
      );
    }
    if (req.method() === "PATCH")
      return json(route, resume("r1", "Jane", null));
    return json(route, {});
  });
}

test("paste a job, answer a gap, approve the bullet, land on the follow-up", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/workspace");

  // Original resume: the Review tab starts with the paste box.
  await page.getByRole("tab", { name: /^(Tailor|Review)/ }).click();
  const box = page.getByRole("textbox", { name: "Job description" });
  await expect(box).toBeFocused();
  const tailor = page.getByRole("button", { name: "Tailor", exact: true });
  await expect(tailor).toBeDisabled();
  await box.fill("Backend engineer\nWe use Kubernetes");
  await tailor.click();

  // Running, then the finished report on the tailored resume.
  await expect(page.getByText("First tailored.tex").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByRole("heading", { name: /What's missing/ }),
  ).toBeVisible();
  await expect(page.getByText("See what already matched")).toBeVisible();
  await expect(
    page.getByText("Must-have", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText("Have you used Kubernetes?")).toBeVisible();

  // Nothing to draft until something is written.
  const draft = page.getByRole("button", { name: /^Draft bullets/ });
  await expect(draft).toBeDisabled();
  await page
    .getByLabel(/Your answer/)
    .fill("I deployed our Django apps on Kubernetes");
  await expect(draft).toBeEnabled();
  await draft.click();

  // Proposed bullet appears, editable.
  const bullet = page.getByLabel("New bullet");
  await expect(bullet).toHaveValue("Deployed Django services on Kubernetes", {
    timeout: 15_000,
  });
  await bullet.fill("Deployed Django services on Kubernetes at Acme");

  const confirm = page.getByRole("button", {
    name: /Add 1 bullet and tailor again/,
  });
  await expect(confirm).toBeEnabled();
  await page.getByLabel("Add this to my resume").uncheck();
  await expect(
    page.getByRole("button", { name: /Add 0 bullets/ }),
  ).toBeDisabled();
  await page.getByLabel("Add this to my resume").check();

  const sent = page.waitForRequest(
    (r) =>
      r.url().endsWith("/tailor-requests/t1/confirm/") && r.method() === "POST",
  );
  await confirm.click();
  expect((await sent).postDataJSON()).toEqual({
    accepted: [
      {
        id: "p1",
        bullet: "Deployed Django services on Kubernetes at Acme",
        skill: "Kubernetes",
        skill_group_id: "g1",
      },
    ],
  });

  // The follow-up's resume shows up in the left list.
  await expect(page.getByText("Second tailored.tex").first()).toBeVisible({
    timeout: 15_000,
  });
});
