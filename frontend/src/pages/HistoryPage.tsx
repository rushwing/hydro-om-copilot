import { useState, useCallback } from "react";
import { useSessionHistory } from "@/hooks/useSessionHistory";
import { useAutoStore } from "@/store/autoStore";
import { riskLevelLabel } from "@/store/diagnosisStore";
import { RootCauseCard } from "@/components/diagnosis/RootCauseCard";
import { ChecklistPanel } from "@/components/diagnosis/ChecklistPanel";
import { ReportDraft } from "@/components/diagnosis/ReportDraft";
import { SourcesPanel } from "@/pages/DiagnosisPage";
import type { DiagnosisResult, PendingArchiveItem, RiskLevel } from "@/types/diagnosis";

// ── Local risk colors ─────────────────────────────────────────────────────────

const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800",
};

// ── Human notes persistence ───────────────────────────────────────────────────

const NOTES_KEY = "hydro_om_human_notes";

function loadNotes(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(NOTES_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function saveNotes(notes: Record<string, string>): void {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
}

// ── Human notes + submit ──────────────────────────────────────────────────────

function HumanNotes({
  id,
  onSubmit,
}: {
  id: string;
  onSubmit?: () => void;
}) {
  const [notes, setNotes] = useState<Record<string, string>>(loadNotes);
  const text = notes[id] ?? "";

  const handleChange = useCallback(
    (val: string) => {
      setNotes((prev) => {
        const updated = { ...prev, [id]: val };
        saveNotes(updated);
        return updated;
      });
    },
    [id],
  );

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4 space-y-3">
      <p className="text-xs font-display uppercase tracking-wider text-text-muted">人工处理报告</p>
      <textarea
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="在此记录现场处理过程、结论及后续措施..."
        rows={5}
        className="w-full rounded-lg border border-surface-border bg-surface-elevated px-3 py-2 text-xs text-text-primary placeholder-text-muted resize-y focus:outline-none focus:border-amber/50 focus:ring-1 focus:ring-amber/30 leading-relaxed font-sans"
      />
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-text-muted">内容自动保存至本地</p>
        {onSubmit && (
          <button
            onClick={onSubmit}
            className="px-4 py-2 text-sm font-medium rounded border border-emerald-700 bg-emerald-950/40 text-emerald-400 hover:bg-emerald-950/70 transition-colors"
          >
            提交归档 — 故障已消缺 ✓
          </button>
        )}
      </div>
    </div>
  );
}

// ── Shared full report view ───────────────────────────────────────────────────

interface FullReportProps {
  sessionId: string;
  riskLevel: RiskLevel | null;
  rootCauses: DiagnosisResult["root_causes"];
  checkSteps: DiagnosisResult["check_steps"];
  reportDraft: string | null;
  sources?: string[];
  onSubmit?: () => void;
}

function FullReport({
  sessionId,
  riskLevel,
  rootCauses,
  checkSteps,
  reportDraft,
  sources = [],
  onSubmit,
}: FullReportProps) {
  return (
    <div className="mt-4 pt-4 border-t border-surface-border space-y-4">
      {riskLevel && (
        <span
          className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold font-display tracking-wide ${darkRiskColors[riskLevel]}`}
        >
          {riskLevelLabel[riskLevel]}
        </span>
      )}

      {rootCauses.length > 0 && (
        <section>
          <h3 className="mb-2 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
            根因分析 — TOP {rootCauses.length}
            <div className="flex-1 h-px bg-surface-border" />
          </h3>
          <div className="space-y-2">
            {rootCauses.map((rc) => (
              <RootCauseCard key={rc.rank} cause={rc} />
            ))}
          </div>
        </section>
      )}

      {checkSteps.length > 0 && (
        <section>
          <h3 className="mb-2 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
            检查操作规程 (SOP)
            <div className="flex-1 h-px bg-surface-border" />
          </h3>
          <ChecklistPanel steps={checkSteps} sessionId={sessionId} />
        </section>
      )}

      {reportDraft && <ReportDraft draft={reportDraft} sessionId={sessionId} />}

      {sources.length > 0 && <SourcesPanel sources={sources} />}

      <HumanNotes id={sessionId} onSubmit={onSubmit} />
    </div>
  );
}

// ── Timestamp helper ──────────────────────────────────────────────────────────

function Timestamp({ iso }: { iso: string | number }) {
  return (
    <span className="font-mono text-xs text-text-secondary bg-surface-elevated border border-surface-border px-2 py-0.5 rounded">
      {new Date(iso).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}

// ── Pending card ──────────────────────────────────────────────────────────────

function PendingCard({
  item,
  onComplete,
}: {
  item: PendingArchiveItem;
  onComplete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-amber p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-text-primary text-sm">{item.unit_id}</span>
            <span className="text-xs text-text-secondary">{item.fault_types.join(", ")}</span>
            {item.source === "unprocessed_fault" && (
              <span className="text-xs px-1.5 py-0.5 rounded border border-amber/30 bg-amber/10 text-amber">
                未完成诊断
              </span>
            )}
            {item.source === "manual_pending" && (
              <span className="text-xs px-1.5 py-0.5 rounded border border-blue-800/60 bg-blue-950/30 text-blue-400">
                人工诊断
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-text-muted">故障触发</span>
            <Timestamp iso={item.triggered_at} />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {item.risk_level && (
            <span
              className={`rounded border px-2 py-0.5 text-xs font-semibold font-display tracking-wide ${darkRiskColors[item.risk_level]}`}
            >
              {riskLevelLabel[item.risk_level]}
            </span>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-text-secondary hover:text-text-primary border border-surface-border px-2 py-1 rounded transition-colors"
          >
            {expanded ? "收起" : "查看详情"}
          </button>
        </div>
      </div>

      {expanded && (
        <FullReport
          sessionId={item.id}
          riskLevel={item.risk_level}
          rootCauses={item.root_causes}
          checkSteps={item.check_steps}
          reportDraft={item.report_draft}
          onSubmit={() => onComplete(item.id)}
        />
      )}
    </div>
  );
}

// ── Manual archived card ──────────────────────────────────────────────────────

function ManualArchivedCard({
  record,
}: {
  record: ReturnType<typeof useSessionHistory>["history"][number];
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-surface-border hover:border-l-amber p-4 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-1.5">
          <p className="line-clamp-1 text-sm text-text-primary">{record.query}</p>
          <div className="flex flex-wrap items-center gap-2">
            {record.result.unit_id && (
              <span className="text-xs text-text-secondary">{record.result.unit_id}</span>
            )}
            <span className="text-[10px] text-text-muted">诊断时间</span>
            <Timestamp iso={record.timestamp} />
            {record.result.root_causes.length > 0 && (
              <span className="text-xs text-text-muted">
                · {record.result.root_causes.length} 个根因
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`rounded border px-2 py-0.5 text-xs font-semibold font-display tracking-wide ${darkRiskColors[record.result.risk_level]}`}
          >
            {riskLevelLabel[record.result.risk_level]}
          </span>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-text-secondary hover:text-text-primary border border-surface-border px-2 py-1 rounded transition-colors"
          >
            {expanded ? "收起" : "查看详情"}
          </button>
        </div>
      </div>

      {expanded && (
        <FullReport
          sessionId={record.id}
          riskLevel={record.result.risk_level}
          rootCauses={record.result.root_causes}
          checkSteps={record.result.check_steps}
          reportDraft={record.result.report_draft ?? null}
          sources={record.result.sources}
        />
      )}
    </div>
  );
}

// ── Auto archived card ────────────────────────────────────────────────────────

function AutoArchivedCard({ item }: { item: PendingArchiveItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-emerald-800 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-text-primary text-sm">{item.unit_id}</span>
            <span className="text-xs text-text-secondary">{item.fault_types.join(", ")}</span>
            <span className="text-xs px-1.5 py-0.5 rounded border border-emerald-800 bg-emerald-950/20 text-emerald-400">
              已消缺
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-text-muted">故障触发</span>
            <Timestamp iso={item.triggered_at} />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {item.risk_level && (
            <span
              className={`rounded border px-2 py-0.5 text-xs font-semibold font-display tracking-wide ${darkRiskColors[item.risk_level]}`}
            >
              {riskLevelLabel[item.risk_level]}
            </span>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-text-secondary hover:text-text-primary border border-surface-border px-2 py-1 rounded transition-colors"
          >
            {expanded ? "收起" : "查看详情"}
          </button>
        </div>
      </div>

      {expanded && (
        <FullReport
          sessionId={item.id}
          riskLevel={item.risk_level}
          rootCauses={item.root_causes}
          checkSteps={item.check_steps}
          reportDraft={item.report_draft}
        />
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type TabKey = "待处理" | "已归档";

export function HistoryPage() {
  const { history, clearHistory } = useSessionHistory();
  const { pendingArchive, completePending } = useAutoStore();
  const [tab, setTab] = useState<TabKey>("待处理");

  const pendingItems = pendingArchive.filter((x) => !x.completed);
  const archivedAutoItems = pendingArchive.filter((x) => x.completed);

  // Merge manual + completed-auto records sorted by timestamp desc
  const allArchived = [
    ...history.map((r) => ({
      ts: r.timestamp,
      el: <ManualArchivedCard key={r.id} record={r} />,
    })),
    ...archivedAutoItems.map((item) => ({
      ts: new Date(item.archived_at).getTime(),
      el: <AutoArchivedCard key={item.id} item={item} />,
    })),
  ].sort((a, b) => b.ts - a.ts);

  const tabs: TabKey[] = ["待处理", "已归档"];

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-wide text-text-primary">
            历史诊断记录
          </h1>
          <p className="text-xs text-text-muted mt-1">
            {tab === "待处理"
              ? `${pendingItems.length} 条待处理`
              : `${allArchived.length} 条已归档`}
          </p>
        </div>
        {tab === "已归档" && history.length > 0 && (
          <button
            onClick={clearHistory}
            className="text-xs text-red-500/70 border border-red-900/50 px-3 py-1.5 rounded hover:bg-red-950/30 hover:text-red-400 transition-colors"
          >
            清空手动记录
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-surface-border">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t
                ? "text-amber border-amber"
                : "text-text-secondary border-transparent hover:text-text-primary"
            }`}
          >
            {t}
            {t === "待处理" && pendingItems.length > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-amber/10 border border-amber/30 text-amber">
                {pendingItems.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "待处理" && (
        <div className="space-y-3">
          {pendingItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="text-5xl opacity-10 mb-4 select-none">✓</div>
              <p className="font-display text-sm uppercase tracking-widest text-text-muted">
                暂无待处理记录
              </p>
              <p className="text-xs text-text-muted mt-2">
                点击自动诊断报告中的「稍后处理」将记录移至此处
              </p>
            </div>
          ) : (
            pendingItems.map((item) => (
              <PendingCard key={item.id} item={item} onComplete={completePending} />
            ))
          )}
        </div>
      )}

      {tab === "已归档" && (
        <div className="space-y-2">
          {allArchived.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="text-5xl opacity-10 mb-4 select-none">⚡</div>
              <p className="font-display text-sm uppercase tracking-widest text-text-muted">
                暂无归档记录
              </p>
              <p className="text-xs text-text-muted mt-2">完成一次诊断后，记录将在此展示</p>
            </div>
          ) : (
            allArchived.map((item) => item.el)
          )}
        </div>
      )}
    </div>
  );
}
