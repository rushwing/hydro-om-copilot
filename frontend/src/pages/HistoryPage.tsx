import { useSessionHistory } from "@/hooks/useSessionHistory";
import { riskLevelLabel } from "@/store/diagnosisStore";
import type { RiskLevel } from "@/types/diagnosis";

// Local dark-theme risk colors (same mapping as RiskBadge)
const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800",
};

export function HistoryPage() {
  const { history, clearHistory } = useSessionHistory();

  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="text-5xl opacity-10 mb-4 select-none">⚡</div>
        <p className="font-display text-sm uppercase tracking-widest text-text-muted">
          暂无诊断记录
        </p>
        <p className="text-xs text-text-muted mt-2">完成一次诊断后，记录将在此展示</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-wide text-text-primary">
            历史诊断记录
          </h1>
          <p className="text-xs text-text-muted mt-1">{history.length} 条记录</p>
        </div>
        <button
          onClick={clearHistory}
          className="text-xs text-red-500/70 border border-red-900/50 px-3 py-1.5 rounded hover:bg-red-950/30 hover:text-red-400 transition-colors"
        >
          清空记录
        </button>
      </div>

      <div className="space-y-2">
        {history.map((record) => (
          <div
            key={record.id}
            className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-surface-border hover:border-l-amber p-4 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="line-clamp-1 flex-1 text-sm text-text-primary">{record.query}</p>
              <span
                className={`shrink-0 rounded border px-2 py-0.5 text-xs font-semibold font-display tracking-wide ${darkRiskColors[record.result.risk_level]}`}
              >
                {riskLevelLabel[record.result.risk_level]}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-text-muted">
              {new Date(record.timestamp).toLocaleString("zh-CN")}
              {record.result.unit_id && (
                <span className="ml-2 text-text-secondary">{record.result.unit_id}</span>
              )}
              {record.result.root_causes.length > 0 && (
                <span className="ml-2 text-text-muted">
                  · {record.result.root_causes.length} 个根因
                </span>
              )}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
