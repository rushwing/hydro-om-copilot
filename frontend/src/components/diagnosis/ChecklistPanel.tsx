import { useState, useEffect } from "react";
import type { CheckStep } from "@/types/diagnosis";

// ── Persistence ───────────────────────────────────────────────────────────────

const CHECKLIST_KEY = "hydro_om_checklist_states";

function loadChecklist(sessionId: string): Set<number> {
  try {
    const all = JSON.parse(localStorage.getItem(CHECKLIST_KEY) ?? "{}") as Record<string, number[]>;
    const arr = all[sessionId];
    return Array.isArray(arr) ? new Set<number>(arr) : new Set<number>();
  } catch {
    return new Set<number>();
  }
}

function saveChecklist(sessionId: string, checked: Set<number>): void {
  try {
    const all = JSON.parse(localStorage.getItem(CHECKLIST_KEY) ?? "{}") as Record<string, number[]>;
    all[sessionId] = [...checked];
    localStorage.setItem(CHECKLIST_KEY, JSON.stringify(all));
  } catch {
    // ignore
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

interface ChecklistPanelProps {
  steps: CheckStep[];
  sessionId?: string;
  onAllChecked?: (v: boolean) => void;
  onCheckedChange?: (checked: Set<number>) => void;
}

export function ChecklistPanel({ steps, sessionId, onAllChecked, onCheckedChange }: ChecklistPanelProps) {
  const [checked, setChecked] = useState<Set<number>>(() =>
    sessionId ? loadChecklist(sessionId) : new Set(),
  );

  // Re-initialize when sessionId changes (new result)
  useEffect(() => {
    setChecked(sessionId ? loadChecklist(sessionId) : new Set());
  }, [sessionId]);

  const toggle = (step: number) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(step)) { next.delete(step); } else { next.add(step); }
      if (sessionId) saveChecklist(sessionId, next);
      return next;
    });

  const completedCount = checked.size;
  const totalCount = steps.length;
  const allChecked = totalCount === 0 || completedCount === totalCount;
  const completionPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 100;

  useEffect(() => {
    onAllChecked?.(allChecked);
  }, [allChecked, onAllChecked]);

  useEffect(() => {
    onCheckedChange?.(checked);
  }, [checked, onCheckedChange]);

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card overflow-hidden">
      <div className="space-y-0 divide-y divide-surface-border">
        {steps.map((s) => {
          const isDone = checked.has(s.step);
          const stepLabel = String(s.step).padStart(2, "0");
          return (
            <div
              key={s.step}
              className={`p-4 transition-colors ${
                isDone ? "bg-emerald-950/20" : "bg-transparent hover:bg-surface-elevated/50"
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Custom amber checkbox */}
                <button
                  type="button"
                  onClick={() => toggle(s.step)}
                  className={`mt-0.5 h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors ${
                    isDone
                      ? "border-emerald-500 bg-emerald-500"
                      : "border-surface-border bg-surface-elevated hover:border-amber/60"
                  }`}
                  aria-label={isDone ? "取消勾选" : "标记完成"}
                >
                  {isDone && (
                    <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 10 10">
                      <path
                        d="M1.5 5L4 7.5L8.5 2.5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="font-display text-xs font-bold text-amber tracking-wider shrink-0">
                      STEP {stepLabel}
                    </span>
                    <span
                      className={`text-sm font-medium transition-colors ${
                        isDone ? "text-text-muted line-through" : "text-text-primary"
                      }`}
                    >
                      {s.action}
                    </span>
                  </div>
                  {s.expected && (
                    <p className="text-xs text-text-muted mt-0.5">
                      预期结果：{s.expected}
                    </p>
                  )}
                  {s.caution && (
                    <div className="mt-2 rounded border border-red-800 bg-red-950/50 px-3 py-1.5 text-xs text-red-400">
                      <span className="font-semibold font-display">⚠ CAUTION: </span>
                      {s.caution}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Completion bar */}
      <div className="border-t border-surface-border bg-surface-elevated px-4 py-2">
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="font-display text-text-muted uppercase tracking-wider">进度</span>
          <span className="text-text-secondary">
            <span className="text-amber font-semibold">{completedCount}</span> / {totalCount} 步骤已完成
          </span>
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-surface-border">
          <div
            className="h-full rounded-full bg-amber transition-all duration-500"
            style={{ width: `${completionPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
