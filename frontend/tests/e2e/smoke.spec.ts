/**
 * Smoke E2E test — verifies the app shell loads without a real backend.
 *
 * Backend SSE and health calls are intercepted via page.route() so no real
 * server or LLM is required. The SSE body is a minimal inline response
 * (avoids Node.js fs/path imports which are outside the bundler tsconfig).
 *
 * Run:  npm run e2e          (requires `npm run dev` running on :5173)
 */

import { test, expect } from "@playwright/test";

const MINIMAL_SSE = [
  "event: status",
  'data: {"node": "symptom_parser", "phase": "start"}',
  "",
  "event: done",
  "data: {}",
  "",
].join("\n");

test.describe("App shell smoke @P0", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/diagnosis/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: MINIMAL_SSE,
      }),
    );

    await page.route("**/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      }),
    );
  });

  test("page root element is visible", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#root")).toBeVisible();
  });

  test("navigation renders without JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    expect(errors).toHaveLength(0);
  });
});
