import { useState, useCallback } from "react";
import type { DiagnosisResult } from "@/types/diagnosis";

export interface SessionRecord {
  id: string;
  query: string;
  timestamp: number;
  result: DiagnosisResult;
}

const STORAGE_KEY = "hydro_om_session_history";
const MAX_HISTORY = 50;

function loadHistory(): SessionRecord[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function useSessionHistory() {
  const [history, setHistory] = useState<SessionRecord[]>(loadHistory);

  const addRecord = useCallback((query: string, result: DiagnosisResult) => {
    setHistory((prev) => {
      const record: SessionRecord = {
        id: result.session_id,
        query,
        timestamp: Date.now(),
        result,
      };
      const updated = [record, ...prev].slice(0, MAX_HISTORY);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setHistory([]);
  }, []);

  return { history, addRecord, clearHistory };
}
