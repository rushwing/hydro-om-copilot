/**
 * BUG-001 regression — InputPanel lock during manual diagnosis.
 *
 * Verifies that all interactive controls in the InputPanel are disabled while
 * an SSE diagnosis stream is in progress, and are re-enabled after the stream
 * completes with a `done` event.
 *
 * No real backend required — SSE is intercepted via page.route().
 *
 * TC: TC-BUG-001-001
 * Run:  npm run e2e
 */

import { test, expect } from "@playwright/test";

const DIAGNOSIS_QUERY = "测试描述，触发手动诊断 BUG-001 回归";

const MINIMAL_SSE = [
  "event: status",
  'data: {"node":"symptom_parser","phase":"start"}',
  "",
  "event: status",
  'data: {"node":"symptom_parser","phase":"end"}',
  "",
  "event: done",
  "data: {}",
  "",
].join("\n");

async function mockHealthRoute(page: import("@playwright/test").Page) {
  await page.route("**/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    }),
  );
}

test.describe("BUG-001 InputPanel lock @P1", () => {
  // ── Test 1: controls disabled while SSE is in-flight ─────────────────────

  test("all input controls are disabled while diagnosis is running", async ({
    page,
  }) => {
    // Route the SSE endpoint but never fulfill — this keeps the request
    // pending indefinitely so isRunning stays true throughout our assertions.
    // isRunning is set synchronously (setPhase("symptom_parser")) before the
    // fetch starts, so the UI locks immediately on form submit.
    await page.route("**/diagnosis/run", () => {
      // Intentionally never calls route.fulfill() / route.continue() / route.abort()
      // so the fetch request hangs and the running state persists.
    });
    await mockHealthRoute(page);

    await page.goto("/");

    // Fill the textarea so the submit button becomes active
    await page.getByPlaceholder(/描述异常现象/).fill(DIAGNOSIS_QUERY);

    // Submit the form — isRunning flips to true synchronously
    await page.getByRole("button", { name: "开始诊断" }).click();

    // Guard: confirm the panel is in running state (abort button visible)
    await expect(page.getByRole("button", { name: "停止诊断" })).toBeVisible();

    // ── Unit selector buttons ──────────────────────────────────────────────
    await expect(page.getByRole("button", { name: "#1机" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "#2机" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "#3机" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "#4机" })).toBeDisabled();

    // ── Device selector buttons ────────────────────────────────────────────
    await expect(page.getByRole("button", { name: "上导轴承" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "下导轴承" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "推力轴承" })).toBeDisabled();

    // ── Anomaly type buttons ───────────────────────────────────────────────
    await expect(page.getByRole("button", { name: "振动" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "温度高" })).toBeDisabled();

    // ── Textarea ───────────────────────────────────────────────────────────
    await expect(page.getByPlaceholder(/描述异常现象/)).toBeDisabled();

    // ── Image upload zone ──────────────────────────────────────────────────
    // When running, the drop zone renders with cursor-not-allowed and opacity-40.
    // Use the border-dashed class which is unique to the upload drop zone.
    const uploadZone = page.locator(".border-dashed");
    await expect(uploadZone).toHaveClass(/cursor-not-allowed/);
    await expect(uploadZone).toHaveClass(/opacity-40/);
  });

  // ── Test 2: controls re-enabled after SSE done event ─────────────────────

  test("all input controls re-enable after diagnosis completes", async ({
    page,
  }) => {
    // Fulfill with a complete SSE stream (status + done) so the hook fires
    // onDone() and transitions phase → "done", making isRunning=false.
    await page.route("**/diagnosis/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: MINIMAL_SSE,
      }),
    );
    await mockHealthRoute(page);

    await page.goto("/");

    await page.getByPlaceholder(/描述异常现象/).fill(DIAGNOSIS_QUERY);
    await page.getByRole("button", { name: "开始诊断" }).click();

    // Wait for the diagnosis to complete — submit button returns
    await expect(
      page.getByRole("button", { name: "开始诊断" }),
    ).toBeVisible({ timeout: 5_000 });

    // ── All controls must be re-enabled ───────────────────────────────────
    await expect(page.getByRole("button", { name: "#1机" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "#2机" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "上导轴承" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "振动" })).toBeEnabled();
    await expect(page.getByPlaceholder(/描述异常现象/)).toBeEnabled();

    // Upload zone should have cursor-pointer (not cursor-not-allowed)
    const uploadZone = page.locator(".border-dashed");
    await expect(uploadZone).not.toHaveClass(/cursor-not-allowed/);
    await expect(uploadZone).toHaveClass(/cursor-pointer/);
  });
});
