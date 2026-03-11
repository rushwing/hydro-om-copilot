import { useEffect } from "react";
import type { AutoDiagnosisRecord, AutoDiagnosisStatus } from "@/types/diagnosis";
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

async function postAutoStop(): Promise<void> {
  await fetch(`${API_BASE}/diagnosis/auto/stop`, { method: "POST" });
}

export function useAutoDiagnosis() {
  const { enabled, setEnabled, setStatus, setResults } = useAutoStore();

  useEffect(() => {
    if (!enabled) return;

    let active = true;

    const poll = async () => {
      try {
        const [status, results] = await Promise.all([fetchAutoStatus(), fetchAutoResults()]);
        if (active) {
          setStatus(status);
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

  const start = async () => {
    await postAutoStart();
    setEnabled(true);
  };

  const stop = async () => {
    await postAutoStop();
    // Keep enabled=true so results remain visible; user can toggle manually
  };

  return { start, stop };
}
