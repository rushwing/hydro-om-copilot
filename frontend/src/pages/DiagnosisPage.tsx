import { useCallback } from "react";
import { InputPanel } from "@/components/diagnosis/InputPanel";
import { StreamingOutput } from "@/components/diagnosis/StreamingOutput";
import { RootCauseCard } from "@/components/diagnosis/RootCauseCard";
import { ChecklistPanel } from "@/components/diagnosis/ChecklistPanel";
import { RiskBadge } from "@/components/diagnosis/RiskBadge";
import { ReportDraft } from "@/components/diagnosis/ReportDraft";
import { useSSEDiagnosis } from "@/hooks/useSSEDiagnosis";
import { useSessionHistory } from "@/hooks/useSessionHistory";
import { useDiagnosisStore } from "@/store/diagnosisStore";
import type { DiagnosisRequest, DiagnosisResult } from "@/types/diagnosis";

const TOPIC_LABELS: Record<string, string> = {
  vibration_swing: "振动与摆度",
  governor_oil: "调速器油压",
  bearing_temp: "轴承温升",
};

function getSourceColor(docId: string): string {
  if (docId.startsWith("L1.")) return "text-blue-400 bg-blue-950 border-blue-800";
  if (docId.startsWith("L2.TOPIC.")) return "text-amber bg-amber-950 border-amber-800";
  if (docId.startsWith("L2.SUPPORT.RULE.")) return "text-red-400 bg-red-950 border-red-800";
  if (docId.startsWith("L2.SUPPORT.CASE.")) return "text-emerald-400 bg-emerald-950 border-emerald-800";
  return "text-text-secondary bg-surface-elevated border-surface-border";
}

function AnomalySummary({ result }: { result: DiagnosisResult }) {
  return (
    <div className="animate-result rounded-lg border border-surface-border bg-surface-elevated px-4 py-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-display uppercase tracking-wider text-xs text-text-muted">检测到异常</span>
        {result.unit_id && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded border border-surface-border bg-surface-card text-text-secondary text-xs">
            <span className="text-amber">◈</span> {result.unit_id}
          </span>
        )}
        {result.topic && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded border border-amber/30 bg-amber/10 text-amber text-xs">
            <span>◆</span> {TOPIC_LABELS[result.topic] ?? result.topic}
          </span>
        )}
      </div>
    </div>
  );
}

function SourcesPanel({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null;
  return (
    <div
      className="animate-result rounded-lg border border-surface-border bg-surface-card p-4"
      style={{ animationDelay: "0.35s", opacity: 0 }}
    >
      <h3 className="font-display text-xs uppercase tracking-wider text-text-muted mb-3">
        引用知识库文档
      </h3>
      <div className="flex flex-wrap gap-2">
        {sources.map((docId) => (
          <span
            key={docId}
            className={`px-2 py-0.5 rounded border text-xs font-mono ${getSourceColor(docId)}`}
          >
            {docId}
          </span>
        ))}
      </div>
    </div>
  );
}

function EmptyResultPanel() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center py-20">
      <div className="mb-4 text-6xl opacity-10 select-none">⚡</div>
      <p className="font-display text-sm uppercase tracking-widest text-text-muted">
        诊断结果将在此展示
      </p>
      <p className="text-text-muted text-xs mt-2 max-w-xs leading-relaxed">
        在左侧选择机组、设备和异常类型，描述故障现象后点击「开始诊断」
      </p>
    </div>
  );
}

export function DiagnosisPage() {
  const { run, abort } = useSSEDiagnosis();
  const { addRecord } = useSessionHistory();
  const { phase, result } = useDiagnosisStore();

  const isRunning = phase !== "idle" && phase !== "done" && phase !== "error";

  const handleSubmit = useCallback(
    async (request: DiagnosisRequest) => {
      await run(request);
      const current = useDiagnosisStore.getState().result;
      if (current) addRecord(request.query, current);
    },
    [run, addRecord],
  );

  return (
    <div className="flex h-[calc(100vh-52px)]">
      {/* Left panel — input + streaming */}
      <aside className="w-5/12 sticky top-[52px] overflow-y-auto border-r border-surface-border p-6 space-y-4">
        <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-amber p-5">
          <div className="mb-4 flex items-center gap-2">
            <span className="font-display text-xs uppercase tracking-widest text-text-muted">
              故障参数输入
            </span>
            <div className="flex-1 h-px bg-surface-border" />
          </div>
          <InputPanel onSubmit={handleSubmit} onAbort={abort} isRunning={isRunning} />
        </div>
        <StreamingOutput />
      </aside>

      {/* Right panel — results */}
      <main className="w-7/12 overflow-y-auto p-6 space-y-4">
        {result ? (
          <>
            <AnomalySummary result={result} />

            <div
              className="animate-result flex flex-wrap items-center gap-3"
              style={{ animationDelay: "0.05s", opacity: 0 }}
            >
              <RiskBadge level={result.risk_level} escalation={result.escalation_required} />
              {result.escalation_reason && (
                <span className="text-sm text-red-400">{result.escalation_reason}</span>
              )}
            </div>

            {result.root_causes.length > 0 && (
              <section>
                <h2 className="mb-3 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
                  根因分析 — TOP {result.root_causes.length}
                  <div className="flex-1 h-px bg-surface-border" />
                </h2>
                <div className="space-y-3">
                  {result.root_causes.map((rc, i) => (
                    <div
                      key={rc.rank}
                      className="animate-result"
                      style={{ animationDelay: `${0.1 + i * 0.08}s`, opacity: 0 }}
                    >
                      <RootCauseCard cause={rc} />
                    </div>
                  ))}
                </div>
              </section>
            )}

            {result.check_steps.length > 0 && (
              <section>
                <h2 className="mb-3 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
                  检查操作规程 (SOP)
                  <div className="flex-1 h-px bg-surface-border" />
                </h2>
                <div
                  className="animate-result"
                  style={{ animationDelay: "0.25s", opacity: 0 }}
                >
                  <ChecklistPanel steps={result.check_steps} />
                </div>
              </section>
            )}

            {result.report_draft && (
              <div
                className="animate-result"
                style={{ animationDelay: "0.3s", opacity: 0 }}
              >
                <ReportDraft draft={result.report_draft} sessionId={result.session_id} />
              </div>
            )}

            <SourcesPanel sources={result.sources} />
          </>
        ) : (
          <EmptyResultPanel />
        )}
      </main>
    </div>
  );
}
