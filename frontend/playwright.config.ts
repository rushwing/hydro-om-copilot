import { defineConfig, devices } from "@playwright/test";

// Prevent system HTTP proxy from intercepting localhost requests.
// Common on dev machines with clash/v2ray (e.g. http_proxy=127.0.0.1:7897).
// Only set if absent so CI environments are unaffected.
if (!process.env.NO_PROXY) {
  process.env.NO_PROXY = "localhost,127.0.0.1";
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Playwright auto-starts the Vite dev server before running tests and
  // tears it down afterwards. npm run e2e is self-contained — no manual
  // `npm run dev` required. reuseExistingServer lets local devs skip the
  // boot wait if they already have Vite running on :5173.
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
