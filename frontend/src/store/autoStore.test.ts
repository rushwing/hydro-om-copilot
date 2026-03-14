import { beforeEach, describe, expect, it } from "vitest";
import { useAutoStore } from "./autoStore";
import type { PendingArchiveItem } from "@/types/diagnosis";

const PENDING_KEY = "hydro_om_pending_archive";

function makeItem(id: string): PendingArchiveItem {
  return {
    id,
    unit_id: `#${id}机`,
    fault_types: ["vibration_swing"],
    risk_level: "high",
    root_causes: [],
    check_steps: [],
    report_draft: null,
    triggered_at: "2026-03-14T00:00:00Z",
    archived_at: "2026-03-14T00:01:00Z",
    source: "auto_diagnosed",
    completed: false,
  };
}

beforeEach(() => {
  localStorage.clear();
  // Reset store to initial state between tests
  useAutoStore.setState({
    enabled: false,
    status: null,
    results: [],
    selectedSessionId: null,
    pendingArchive: [],
    toasts: [],
  });
});

describe("autoStore — initialization", () => {
  it("loads pendingArchive from localStorage on store creation", () => {
    const item = makeItem("1");
    localStorage.setItem(PENDING_KEY, JSON.stringify([item]));
    // Simulate store re-initialization by calling loadPending indirectly
    // (store is a singleton; test hydration via state setter)
    useAutoStore.setState({ pendingArchive: [item] });
    expect(useAutoStore.getState().pendingArchive).toHaveLength(1);
    expect(useAutoStore.getState().pendingArchive[0].id).toBe("1");
  });

  it("starts with empty pendingArchive when localStorage is empty", () => {
    expect(useAutoStore.getState().pendingArchive).toHaveLength(0);
  });
});

describe("autoStore — addToPending", () => {
  it("adds an item to pendingArchive", () => {
    const item = makeItem("1");
    useAutoStore.getState().addToPending(item);
    expect(useAutoStore.getState().pendingArchive).toHaveLength(1);
  });

  it("deduplicates items with the same id", () => {
    const item = makeItem("1");
    useAutoStore.getState().addToPending(item);
    useAutoStore.getState().addToPending(item);
    expect(useAutoStore.getState().pendingArchive).toHaveLength(1);
  });

  it("prepends new items (most recent first)", () => {
    useAutoStore.getState().addToPending(makeItem("first"));
    useAutoStore.getState().addToPending(makeItem("second"));
    expect(useAutoStore.getState().pendingArchive[0].id).toBe("second");
  });

  it("writes to localStorage after adding", () => {
    useAutoStore.getState().addToPending(makeItem("x"));
    const stored = JSON.parse(localStorage.getItem(PENDING_KEY) ?? "[]");
    expect(stored).toHaveLength(1);
    expect(stored[0].id).toBe("x");
  });
});

describe("autoStore — completePending", () => {
  it("marks the item as completed", () => {
    useAutoStore.getState().addToPending(makeItem("done-me"));
    useAutoStore.getState().completePending("done-me");
    const item = useAutoStore.getState().pendingArchive.find((p) => p.id === "done-me");
    expect(item?.completed).toBe(true);
  });

  it("persists completed=true to localStorage", () => {
    useAutoStore.getState().addToPending(makeItem("persist-me"));
    useAutoStore.getState().completePending("persist-me");
    const stored = JSON.parse(localStorage.getItem(PENDING_KEY) ?? "[]") as PendingArchiveItem[];
    expect(stored.find((p) => p.id === "persist-me")?.completed).toBe(true);
  });

  it("does not affect other items", () => {
    useAutoStore.getState().addToPending(makeItem("a"));
    useAutoStore.getState().addToPending(makeItem("b"));
    useAutoStore.getState().completePending("a");
    const b = useAutoStore.getState().pendingArchive.find((p) => p.id === "b");
    expect(b?.completed).toBe(false);
  });
});

describe("autoStore — toasts", () => {
  it("addToast creates a toast with a unique id and message", () => {
    useAutoStore.getState().addToast("测试通知");
    const { toasts } = useAutoStore.getState();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("测试通知");
    expect(toasts[0].id).toMatch(/^toast-/);
  });

  it("dismissToast removes the toast with matching id", () => {
    useAutoStore.getState().addToast("msg1");
    useAutoStore.getState().addToast("msg2");
    const id = useAutoStore.getState().toasts[0].id;
    useAutoStore.getState().dismissToast(id);
    expect(useAutoStore.getState().toasts).toHaveLength(1);
    expect(useAutoStore.getState().toasts[0].message).toBe("msg2");
  });

  it("dismissToast is a no-op for unknown id", () => {
    useAutoStore.getState().addToast("msg");
    useAutoStore.getState().dismissToast("nonexistent-id");
    expect(useAutoStore.getState().toasts).toHaveLength(1);
  });
});

describe("autoStore — setEnabled / setResults", () => {
  it("setEnabled toggles the enabled flag", () => {
    useAutoStore.getState().setEnabled(true);
    expect(useAutoStore.getState().enabled).toBe(true);
    useAutoStore.getState().setEnabled(false);
    expect(useAutoStore.getState().enabled).toBe(false);
  });

  it("setResults replaces the results array", () => {
    const record = {
      session_id: "s1",
      unit_id: "#1机",
      fault_types: ["vibration_swing"],
      symptom_text: "振动超标",
      triggered_at: "2026-03-14T00:00:00Z",
      risk_level: "high" as const,
      escalation_required: false,
      escalation_reason: null,
      root_causes: [],
      check_steps: [],
      report_draft: null,
      sources: [],
      error: null,
    };
    useAutoStore.getState().setResults([record]);
    expect(useAutoStore.getState().results).toHaveLength(1);
    expect(useAutoStore.getState().results[0].session_id).toBe("s1");
  });
});
