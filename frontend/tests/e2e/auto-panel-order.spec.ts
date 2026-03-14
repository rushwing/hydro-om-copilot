/**
 * BUG-002 regression — AutoDiagnosisPanel render order and unit state semantics.
 *
 * Verifies that after BUG-002 fix:
 *   A. Section order: UnitStatusGrid precedes EpochIndicator
 *   B. epoch_num=0 → all unit tiles neutral (—)
 *   C. Unit in pending_queue → red tile (⚠ 待处理)
 *   D. No pending fault, epoch_num>0 → green tile (✓ 正常)
 *   E. current non-null → timestamp shown in CurrentDiagnosisCard
 *
 * All backend calls are intercepted via page.route() — no real server required.
 *
 * TC: TC-BUG-002-001
 * Run:  npm run e2e
 */

import { test, expect, type Page } from "@playwright/test";

// ── Base status fixture ───────────────────────────────────────────────────────

type DeepPartial<T> = { [K in keyof T]?: T[K] };

interface StatusShape {
  running: boolean;
  is_simulated: boolean;
  current: null | {
    session_id: string;
    unit_id: string;
    fault_types: string[];
    phase: string;
    stream_preview: string;
    sensor_data: never[];
    started_at: string;
  };
  pending_queue: { unit_id: string; fault_types: string[]; symptom_preview: string; queued_at: string }[];
  completed_count: number;
  unit_cooldowns: Record<string, number>;
  epoch_num: number;
  epoch_elapsed_s: number;
  epoch_phase: string;
}

function makeStatus(overrides: DeepPartial<StatusShape> = {}): StatusShape {
  return {
    running: false,
    is_simulated: true,
    current: null,
    pending_queue: [],
    completed_count: 0,
    unit_cooldowns: { "#1机": 0, "#2机": 0, "#3机": 0, "#4机": 0 },
    epoch_num: 1,
    epoch_elapsed_s: 120,
    epoch_phase: "NORMAL",
    ...overrides,
  } as StatusShape;
}

// ── Route setup + auto-mode entry ─────────────────────────────────────────────

async function enterAutoMode(page: Page, status: StatusShape) {
  await page.route("**/health", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    }),
  );
  await page.route("**/diagnosis/auto/status", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(status),
    }),
  );
  await page.route("**/diagnosis/auto-results", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/diagnosis/auto/start", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
  await page.route("**/diagnosis/auto/reset-cooldowns", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
  // Prevent any manual-diagnosis SSE from interfering
  await page.route("**/diagnosis/run", () => {});

  await page.goto("/");

  // Click the nav toggle to enable auto mode (calls start() → setEnabled(true))
  await page.getByRole("button", { name: "自动诊断" }).click();

  // Wait for AutoDiagnosisPanel to mount and first poll data to arrive
  await expect(page.getByText("各机组故障状态")).toBeVisible({ timeout: 5_000 });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("BUG-002 AutoDiagnosisPanel order & semantics @P1", () => {
  // A — render order ──────────────────────────────────────────────────────────
  test("UnitStatusGrid renders above EpochIndicator", async ({ page }) => {
    await enterAutoMode(page, makeStatus());

    const unitGridBox = await page.getByText("各机组故障状态").boundingBox();
    const epochBox = await page.getByText("传感器采集周期（模拟）").boundingBox();

    expect(unitGridBox).not.toBeNull();
    expect(epochBox).not.toBeNull();
    // The unit grid heading must appear higher in the viewport than the epoch indicator heading
    expect(unitGridBox!.y).toBeLessThan(epochBox!.y);
  });

  // B — neutral state when epoch_num=0 ────────────────────────────────────────
  test("all unit tiles show neutral state before first epoch completes", async ({
    page,
  }) => {
    await enterAutoMode(page, makeStatus({ epoch_num: 0 }));

    // Subtitle should explain the neutral state
    await expect(page.getByText("首轮采集尚未完成，等待数据…")).toBeVisible();

    // All 4 unit tiles should display a dash indicator (one per unit)
    await expect(page.getByText("—")).toHaveCount(4);

    // No fault or OK indicators should be present
    await expect(page.getByText("⚠ 待处理")).not.toBeVisible();
    await expect(page.getByText("✓ 正常")).not.toBeVisible();
  });

  // C — fault unit shows red ──────────────────────────────────────────────────
  test("unit in pending_queue shows red fault indicator", async ({ page }) => {
    await enterAutoMode(
      page,
      makeStatus({
        epoch_num: 2,
        pending_queue: [
          {
            unit_id: "#2机",
            fault_types: ["振动"],
            symptom_preview: "摆度超限",
            queued_at: new Date().toISOString(),
          },
        ],
      }),
    );

    // Exactly one fault indicator — only #2机 is in the queue
    await expect(page.getByText("⚠ 待处理")).toHaveCount(1);

    // The remaining 3 units (#1机, #3机, #4机) should show green OK
    await expect(page.getByText("✓ 正常")).toHaveCount(3);
  });

  // D — no fault units show green ─────────────────────────────────────────────
  test("all unit tiles show green when no pending faults", async ({ page }) => {
    await enterAutoMode(page, makeStatus({ epoch_num: 1, pending_queue: [] }));

    // Subtitle should show the data-available hint
    await expect(page.getByText("红色：存在待处理故障；绿色：暂无故障")).toBeVisible();

    // At least the first unit should display ✓ 正常 (cooldowns are 0 for all)
    await expect(page.getByText("✓ 正常").first()).toBeVisible();

    // No unit should show the fault indicator
    await expect(page.getByText("⚠ 待处理")).not.toBeVisible();
  });

  // E — timestamp in CurrentDiagnosisCard ────────────────────────────────────
  test("CurrentDiagnosisCard displays a relative timestamp from started_at", async ({
    page,
  }) => {
    const startedAt = new Date(Date.now() - 45_000).toISOString(); // 45 s ago

    await enterAutoMode(
      page,
      makeStatus({
        running: true,
        current: {
          session_id: "test-session-bug002",
          unit_id: "#3机",
          fault_types: ["温度高"],
          phase: "reasoning",
          stream_preview: "正在推理…",
          sensor_data: [],
          started_at: startedAt,
        },
      }),
    );

    // CurrentDiagnosisCard heading must be visible
    await expect(page.getByText("当前诊断")).toBeVisible();

    // A relative timestamp in the form "Xs 前" must be displayed
    await expect(page.locator("text=/\\d+s 前/")).toBeVisible();
  });
});
