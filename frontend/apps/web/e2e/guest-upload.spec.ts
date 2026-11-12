import path from "node:path";
import { expect, test } from "@playwright/test";

// frontend/apps/web/e2e -> repo root is four levels up.
const RESUME_PDF = path.resolve(
  __dirname,
  "../../../../Real_Resumes/Resume.pdf",
);

test("guest uploads a resume PDF and lands in the workspace", async ({
  page,
}) => {
  // 1. A fresh Playwright context has no cookies, so this is a brand-new guest
  //    and proxy.ts keeps them on the landing page.
  await page.goto("/");
  await expect(page).toHaveURL(/\/$/);

  // 2. Upload the PDF. The input is `hidden`, but setInputFiles doesn't need
  //    it to be visible.
  await page.locator('input[type="file"]').setInputFiles(RESUME_PDF);

  // 3. The page only navigates once the status poll reports `succeeded`, so
  //    this covers upload -> Celery parse -> poll -> redirect.
  await expect(page).toHaveURL(/\/workspace$/, { timeout: 120_000 });

  // 4. We got the parsed resume, not the empty starter. The parse task names
  //    the resume after the PDF; `document.tex` is only created when the
  //    workspace has no resumes.
  //    (The name also shows in the editor tab, so target the sidebar button.)
  await expect(
    page.getByRole("button", { name: "Resume.tex", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("document.tex")).toHaveCount(0);
});
