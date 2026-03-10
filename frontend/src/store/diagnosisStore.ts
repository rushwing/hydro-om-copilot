import { create } from "zustand";
import type { DiagnosisResult, RiskLevel } from "@/types/diagnosis";

export type DiagnosisPhase =
  | "idle"
  | "symptom_parser"
  | "image_agent"
  | "retrieval"
  | "reasoning"
  | "report_gen"
  | "done"
  | "error";

interface DiagnosisState {
  phase: DiagnosisPhase;
  streamText: string;
  result: DiagnosisResult | null;
  error: string | null;
  sessionId: string | null;

  // Actions
  reset: () => void;
  setPhase: (phase: DiagnosisPhase) => void;
  appendToken: (text: string) => void;
  setResult: (result: DiagnosisResult) => void;
  setError: (msg: string) => void;
  setSessionId: (id: string) => void;
}

export const useDiagnosisStore = create<DiagnosisState>((set) => ({
  phase: "idle",
  streamText: "",
  result: null,
  error: null,
  sessionId: null,

  reset: () =>
    set({ phase: "idle", streamText: "", result: null, error: null }),

  setPhase: (phase) => set({ phase }),

  appendToken: (text) =>
    set((state) => ({ streamText: state.streamText + text })),

  setResult: (result) => set({ result, phase: "done" }),

  setError: (msg) => set({ error: msg, phase: "error" }),

  setSessionId: (id) => set({ sessionId: id }),
}));

// Selectors
export const riskLevelLabel: Record<RiskLevel, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "紧急",
};

export const riskLevelColor: Record<RiskLevel, string> = {
  low: "text-green-700 bg-green-100",
  medium: "text-amber-700 bg-amber-100",
  high: "text-red-700 bg-red-100",
  critical: "text-purple-700 bg-purple-100",
};
