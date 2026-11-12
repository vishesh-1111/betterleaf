import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests run against the real stack: the Next dev server (started below if
 * it isn't already up) and the Django backend + Celery worker, which must be
 * running already (`just up` from the repo root).
 */
export default defineConfig({
  testDir: "./e2e",
  // The upload test waits on a real LLM parse via Celery, so allow it time.
  timeout: 150_000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    // Keep `localhost` (not 127.0.0.1): the backend sets the `bl_session`
    // cookie from localhost:8000 and CORS/CSRF are configured for it.
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
