import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoDiagnosis } from "./useAutoDiagnosis";
import { useAutoStore } from "@/store/autoStore";

// ── Fetch stub helpers ────────────────────────────────────────────────────────

function makeJsonResponse(data: unknown, ok = true): Promise<Response> {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  } as unknown as Response);
}

const idleStatus = {
  running: false,
  is_simulated: true,
  current: null,
  pending_queue: [],
  completed_count: 0,
  unit_cooldowns: {},
  epoch_num: 1,
  epoch_elapsed_s: 0,
  epoch_phase: "NORMAL",
};

beforeEach(() => {
  localStorage.clear();
  useAutoStore.setState({
    enabled: false,
    status: null,
    results: [],
    selectedSessionId: null,
    pendingArchive: [],
    toasts: [],
  });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("useAutoDiagnosis — polling", () => {
  it("does not fetch when enabled=false", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderHook(() => useAutoDiagnosis());
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("immediately polls when enabled=true", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      makeJsonResponse(idleStatus),
    );

    useAutoStore.setState({ enabled: true });
    renderHook(() => useAutoDiagnosis());

    await act(async () => {
      await Promise.resolve(); // flush microtasks
    });

    // status + results = 2 calls
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("polls again after 5 seconds", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      makeJsonResponse(idleStatus),
    );

    useAutoStore.setState({ enabled: true });
    renderHook(() => useAutoDiagnosis());

    await act(async () => {
      await Promise.resolve();
    });

    const callsAfterMount = fetchSpy.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(fetchSpy.mock.calls.length).toBeGreaterThan(callsAfterMount);
  });
});

describe("useAutoDiagnosis — start()", () => {
  it("calls reset-cooldowns, then start, then setEnabled(true)", async () => {
    const calls: string[] = [];

    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.includes("reset-cooldowns")) calls.push("reset-cooldowns");
      else if (u.includes("/start")) calls.push("start");
      else if (u.includes("/status")) calls.push("status");
      else if (u.includes("auto-results")) calls.push("results");
      return makeJsonResponse(idleStatus);
    });

    const { result } = renderHook(() => useAutoDiagnosis());

    await act(async () => {
      await result.current.start();
    });

    expect(calls[0]).toBe("reset-cooldowns");
    expect(calls[1]).toBe("start");
    expect(useAutoStore.getState().enabled).toBe(true);
  });
});

describe("useAutoDiagnosis — stop()", () => {
  it("calls postAutoStop and converts dropped_queue to PendingArchiveItems", async () => {
    const droppedItem = {
      unit_id: "#2机",
      fault_types: ["bearing_temp_cooling"],
      symptom_preview: "轴承温升",
      queued_at: "2026-03-14T00:00:00Z",
    };

    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.includes("/stop")) {
        return makeJsonResponse({ dropped_queue: [droppedItem] });
      }
      return makeJsonResponse(idleStatus);
    });

    const { result } = renderHook(() => useAutoDiagnosis());

    await act(async () => {
      await result.current.stop();
    });

    const { pendingArchive } = useAutoStore.getState();
    expect(pendingArchive).toHaveLength(1);
    expect(pendingArchive[0].unit_id).toBe("#2机");
    expect(pendingArchive[0].source).toBe("unprocessed_fault");
    expect(pendingArchive[0].completed).toBe(false);
  });

  it("handles empty dropped_queue gracefully", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      makeJsonResponse({ dropped_queue: [] }),
    );

    const { result } = renderHook(() => useAutoDiagnosis());

    await act(async () => {
      await result.current.stop();
    });

    expect(useAutoStore.getState().pendingArchive).toHaveLength(0);
  });
});
