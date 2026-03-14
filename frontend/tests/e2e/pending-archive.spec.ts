/**
 * Pending-archive state management E2E tests.
 *
 * All backend calls are intercepted via page.route() — no real server required.
 * localStorage is seeded via page.addInitScript() (runs before app JS) for
 * tests that need pre-existing state.
 *
 * Run:  npm run e2e
 */

import { test, expect } from "@playwright/test";

// ── Full SSE that produces a DiagnosisResult with unit_id "#1机" ──────────────

const FULL_SSE = [
  "event: status",
  'data: {"node":"symptom_parser","phase":"start"}',
  "",
  "event: status",
  'data: {"node":"symptom_parser","phase":"end"}',
  "",
  "event: result",
  'data: {"session_id":"test-session-001","unit_id":"#1机","topic":"vibration_swing","root_causes":[],"check_steps":[],"risk_level":"medium","escalation_required":false,"report_draft":null,"sources":[]}',
  "",
  "event: done",
  "data: {}",
  "",
].join("\n");

// ── Seed item factory ─────────────────────────────────────────────────────────

function makeSeedItem(opts: {
  id: string;
  unit_id: string;
  completed?: boolean;
  source?: string;
}) {
  return {
    id: opts.id,
    unit_id: opts.unit_id,
    fault_types: ["振动与摆度"],
    risk_level: "medium",
    root_causes: [],
    check_steps: [],
    report_draft: null,
    triggered_at: "2026-03-15T08:00:00.000Z",
    archived_at: "2026-03-15T08:05:00.000Z",
    source: opts.source ?? "auto_diagnosed",
    completed: opts.completed ?? false,
  };
}

// ── Common route mocks ────────────────────────────────────────────────────────

async function mockCommonRoutes(page: import("@playwright/test").Page) {
  await page.route("**/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    }),
  );

  await page.route("**/diagnosis/auto/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        running: false,
        is_simulated: false,
        current: null,
        pending_queue: [],
        completed_count: 0,
        unit_cooldowns: {},
        epoch_num: 0,
        epoch_elapsed_s: 0,
        epoch_phase: "NORMAL",
      }),
    }),
  );

  await page.route("**/diagnosis/auto-results", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );

  // start / stop / reset-cooldowns
  await page.route("**/diagnosis/auto/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", dropped_queue: [] }),
    }),
  );

  // default run mock — overridden in Test 1
  await page.route("**/diagnosis/run", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream; charset=utf-8",
      body: ["event: done", "data: {}", ""].join("\n"),
    }),
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("Pending archive state management", () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonRoutes(page);
  });

  // ── Test 1 ─────────────────────────────────────────────────────────────────
  // Full UI flow: submit diagnosis → "稍后处理" → navigate → state survives

  test("稍后处理 → 切页返回 → 待处理 tab 仍保留", async ({ page }) => {
    // Override run mock with full SSE that returns a result
    await page.route("**/diagnosis/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: FULL_SSE,
      }),
    );

    await page.goto("/");

    // Fill the symptom textarea and submit
    await page
      .locator('textarea[placeholder*="描述异常现象"]')
      .fill("#1机振动异常，导叶开度反馈偏差");
    await page.getByRole("button", { name: "开始诊断" }).click();

    // Wait for the result to render (SSE completes → phase becomes "done")
    const pendingBtn = page.getByRole("button", { name: /稍后处理/ });
    await pendingBtn.waitFor({ state: "visible", timeout: 10_000 });
    await pendingBtn.click();

    // Navigate to history — "#1机" should appear in pending tab (default)
    await page.goto("/history");
    await expect(page.getByText("#1机").first()).toBeVisible();

    // Navigate away and back — localStorage persistence check
    await page.goto("/");
    await page.goto("/history");
    await expect(page.getByText("#1机").first()).toBeVisible();
  });

  // ── Test 2 ─────────────────────────────────────────────────────────────────
  // localStorage seed → reload → state survives page refresh

  test("刷新后待处理状态恢复", async ({ page }) => {
    const seed = [makeSeedItem({ id: "seed-001", unit_id: "#1机" })];

    await page.addInitScript((data) => {
      localStorage.clear();
      localStorage.setItem("hydro_om_pending_archive", JSON.stringify(data));
    }, seed);

    await page.goto("/history");
    await expect(page.getByText("#1机").first()).toBeVisible();

    await page.reload();
    await expect(page.getByText("#1机").first()).toBeVisible();
  });

  // ── Test 3 ─────────────────────────────────────────────────────────────────
  // Multiple pending items — new result must not overwrite existing ones

  test("新诊断到来旧结果不被覆盖（多条 pending 均保留）", async ({ page }) => {
    const seed = [
      makeSeedItem({ id: "seed-001", unit_id: "#1机" }),
      makeSeedItem({ id: "seed-002", unit_id: "#2机" }),
    ];

    await page.addInitScript((data) => {
      localStorage.clear();
      localStorage.setItem("hydro_om_pending_archive", JSON.stringify(data));
    }, seed);

    await page.goto("/history");

    await expect(page.getByText("#1机").first()).toBeVisible();
    await expect(page.getByText("#2机").first()).toBeVisible();
  });

  // ── Test 4 ─────────────────────────────────────────────────────────────────
  // Archive flow: pending → expand → submit → moves to archived tab

  test("提交归档 → 移入已归档 tab", async ({ page }) => {
    const seed = [makeSeedItem({ id: "seed-001", unit_id: "#1机" })];

    await page.addInitScript((data) => {
      localStorage.clear();
      localStorage.setItem("hydro_om_pending_archive", JSON.stringify(data));
    }, seed);

    await page.goto("/history");

    // Expand the pending card
    await page.getByRole("button", { name: "查看详情" }).first().click();

    // Click the archive submit button (inside HumanNotes component)
    await page.getByRole("button", { name: /提交归档/ }).click();

    // Switch to 已归档 tab
    await page.getByRole("button", { name: "已归档" }).click();

    // Item should now appear in the archived tab
    await expect(page.getByText("#1机").first()).toBeVisible();
  });
});
