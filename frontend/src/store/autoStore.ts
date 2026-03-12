import { create } from "zustand";
import type {
  AutoDiagnosisRecord,
  AutoDiagnosisStatus,
  PendingArchiveItem,
} from "@/types/diagnosis";

export interface ToastItem {
  id: string;
  message: string;
}

const PENDING_STORAGE_KEY = "hydro_om_pending_archive";

function loadPending(): PendingArchiveItem[] {
  try {
    return JSON.parse(localStorage.getItem(PENDING_STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function savePending(items: PendingArchiveItem[]): void {
  localStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(items));
}

interface AutoStore {
  enabled: boolean;
  status: AutoDiagnosisStatus | null;
  results: AutoDiagnosisRecord[];
  selectedIndex: number;
  pendingArchive: PendingArchiveItem[];
  toasts: ToastItem[];
  setEnabled: (v: boolean) => void;
  setStatus: (s: AutoDiagnosisStatus) => void;
  setResults: (r: AutoDiagnosisRecord[]) => void;
  setSelectedIndex: (i: number) => void;
  addToPending: (item: PendingArchiveItem) => void;
  completePending: (id: string) => void;
  addToast: (message: string) => void;
  dismissToast: (id: string) => void;
}

export const useAutoStore = create<AutoStore>()((set) => ({
  enabled: false,
  status: null,
  results: [],
  selectedIndex: 0,
  pendingArchive: loadPending(),
  setEnabled: (v) => set({ enabled: v }),
  setStatus: (s) => set({ status: s }),
  setResults: (r) => set({ results: r }),
  setSelectedIndex: (i) => set({ selectedIndex: i }),
  addToPending: (item) =>
    set((state) => {
      if (state.pendingArchive.some((p) => p.id === item.id)) return state;
      const updated = [item, ...state.pendingArchive];
      savePending(updated);
      return { pendingArchive: updated };
    }),
  completePending: (id) =>
    set((state) => {
      const updated = state.pendingArchive.map((p) =>
        p.id === id ? { ...p, completed: true } : p,
      );
      savePending(updated);
      return { pendingArchive: updated };
    }),
  toasts: [],
  addToast: (message) =>
    set((state) => ({
      toasts: [...state.toasts, { id: `toast-${Date.now()}-${Math.random()}`, message }],
    })),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
