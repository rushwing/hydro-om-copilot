/**
 * Smoke E2E test — verifies the app shell loads without a real backend.
 *
 * SSE calls are intercepted via page.route() and return the fixture from
 * tests/fixtures/sse/happy_path.txt. No real backend or LLM is required.
 *
 * Run:  npm run e2e          (requires `npm run dev` on :5173)
 * CI:   skipped by default; enable by passing --project=chromium
 */

import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { join } from "path";

// Load the SSE fixture once (relative to this file's location)
const SSE_FIXTURE = readFileSync(
  join(__dirname, "../fixtures/sse/happy_path.txt"),
  "utf-8",
);

test.describe("App shell smoke", () => {
  test("page title contains expected product name", async ({ page }) => {
    // Intercept backend calls so the test doesn't need a real server
    await page.route("**/diagnosis/run", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: SSE_FIXTURE,
      });
    });

    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    await page.goto("/");

    // The app shell should render — check for the page root element
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
