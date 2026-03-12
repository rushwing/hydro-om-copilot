import { useCallback, useEffect } from "react";
import type {
  AutoDiagnosisRecord,
  AutoDiagnosisStatus,
  PendingArchiveItem,
} from "@/types/diagnosis";
import { useAutoStore } from "@/store/autoStore";

const API_BASE = "http://localhost:8000";

async function fetchAutoStatus(): Promise<AutoDiagnosisStatus> {
  const res = await fetch(`${API_BASE}/diagnosis/auto/status`);
  if (!res.ok) throw new Error(`status ${res.status}`);
  return res.json();
}

async function fetchAutoResults(): Promise<AutoDiagnosisRecord[]> {
  const res = await fetch(`${API_BASE}/diagnosis/auto-results`);
  if (!res.ok) throw new Error(`status ${res.status}`);
  return res.json();
}

async function postAutoStart(): Promise<void> {
  await fetch(`${API_BASE}/diagnosis/auto/start`, { method: "POST" });
}

async function postAutoStop(): Promise<{ dropped_queue: import("@/types/diagnosis").PendingFaultItem[] }> {
  const res = await fetch(`${API_BASE}/diagnosis/auto/stop`, { method: "POST" });
  if (!res.ok) return { dropped_queue: [] };
  return res.json();
}

async function postResetCooldowns(): Promise<void> {
  await fetch(`${API_BASE}/diagnosis/auto/reset-cooldowns`, { method: "POST" });
}

export function useAutoDiagnosis() {
  const { enabled, setEnabled, setStatus, setResults, addToPending } =
    useAutoStore();

  useEffect(() => {
    if (!enabled) return;

    let active = true;

    const poll = async () => {
      try {
        const [statusData, results] = await Promise.all([
          fetchAutoStatus(),
          fetchAutoResults(),
        ]);
        if (active) {
          setStatus(statusData);
          setResults(results);
        }
      } catch {
        // network errors are silently swallowed; UI retains last known state
      }
    };

    poll();
    const id = setInterval(poll, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [enabled, setStatus, setResults]);

  const resetCooldowns = useCallback(async () => {
    await postResetCooldowns();
  }, []);

  const start = async () => {
    await resetCooldowns();
    await postAutoStart();
    setEnabled(true);
  };

  const stop = async () => {
    // Backend atomically clears _pending and returns the snapshot — use that
    // instead of stale polled status to avoid archiving items the worker
    // already started processing.
    const { dropped_queue } = await postAutoStop();
    const now = new Date().toISOString();
    for (const item of dropped_queue) {
      addToPending({
        id: `unprocessed-${item.unit_id}-${item.queued_at}`,
        unit_id: item.unit_id,
        fault_types: item.fault_types,
        risk_level: null,
        root_causes: [],
        check_steps: [],
        report_draft: null,
        triggered_at: item.queued_at,
        archived_at: now,
        source: "unprocessed_fault",
        completed: false,
      } satisfies PendingArchiveItem);
    }
    // Keep enabled=true so results remain visible; user can toggle manually
  };

  return { start, stop, resetCooldowns };
}
