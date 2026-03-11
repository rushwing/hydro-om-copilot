import { create } from "zustand";
import type { AutoDiagnosisRecord, AutoDiagnosisStatus } from "@/types/diagnosis";

interface AutoStore {
  enabled: boolean;
  status: AutoDiagnosisStatus | null;
  results: AutoDiagnosisRecord[];
  setEnabled: (v: boolean) => void;
  setStatus: (s: AutoDiagnosisStatus) => void;
  setResults: (r: AutoDiagnosisRecord[]) => void;
}

export const useAutoStore = create<AutoStore>()((set) => ({
  enabled: false,
  status: null,
  results: [],
  setEnabled: (v) => set({ enabled: v }),
  setStatus: (s) => set({ status: s }),
  setResults: (r) => set({ results: r }),
}));
