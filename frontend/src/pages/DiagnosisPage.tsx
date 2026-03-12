import { useCallback, useEffect, useRef, useState } from "react";
import { InputPanel } from "@/components/diagnosis/InputPanel";
import { StreamingOutput } from "@/components/diagnosis/StreamingOutput";
import { RootCauseCard } from "@/components/diagnosis/RootCauseCard";
import { ChecklistPanel } from "@/components/diagnosis/ChecklistPanel";
import { RiskBadge } from "@/components/diagnosis/RiskBadge";
import { ReportDraft } from "@/components/diagnosis/ReportDraft";
import { AutoDiagnosisPanel } from "@/components/auto/AutoDiagnosisPanel";
import { useSSEDiagnosis } from "@/hooks/useSSEDiagnosis";
import { useSessionHistory } from "@/hooks/useSessionHistory";
import { useDiagnosisStore } from "@/store/diagnosisStore";
import { useAutoStore } from "@/store/autoStore";
import logoUrl from "@/assets/logo.svg";
import type {
  DiagnosisRequest,
  DiagnosisResult,
  PendingArchiveItem,
  RiskLevel,
} from "@/types/diagnosis";

// ── Human notes helpers (shared key with HistoryPage) ─────────────────────────

const NOTES_KEY = "hydro_om_human_notes";

function loadAllNotes(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(NOTES_KEY) ?? "{}"); } catch { return {}; }
}

function saveAllNotes(notes: Record<string, string>): void {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
}

const RISK_LEVEL_CN: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "严重风险",
};

function buildReportTemplate(result: DiagnosisResult, query: string): string {
  const now = new Date().toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
  const topCause = result.root_causes[0];
  const lines = [
    `【故障处理记录】`,
    ``,
    `机组：${result.unit_id ?? ""}`,
    `故障类型：${TOPIC_LABELS[result.topic ?? ""] ?? result.topic ?? ""}`,
    `告警时间：${now}`,
    `发现方式：□ 传感器自动告警  □ 人工巡检`,
    ``,
    `【异常现象描述】`,
    query || `（请填写现场异常现象）`,
    ``,
    `【AI 诊断结论】`,
    `风险等级：${RISK_LEVEL_CN[result.risk_level] ?? result.risk_level}`,
  ];
  if (topCause) lines.push(`主要根因：${topCause.title}`);
  if (result.escalation_required && result.escalation_reason) {
    lines.push(`升级建议：${result.escalation_reason}`);
  }
  lines.push(
    ``,
    `【现场核查情况】`,
    `（请填写现场实际核查发现）`,
    ``,
    `【处理措施】`,
    `（完成 SOP 检查步骤后将自动填入，请补充各步骤排查结果）`,
    ``,
    `【处置结果】`,
    `□ 故障消除，设备已恢复正常运行`,
    `□ 临时处理，需跟踪观察`,
    `□ 已上报升级，等待检修`,
    `恢复时间：`,
    ``,
    `【后续建议】`,
    `（请填写预防措施及跟踪计划）`,
    ``,
    `【处置人员】`,
    `值班工程师：                    日期：${now.slice(0, 10)}`,
    `技术主管（如需）：              日期：`,
  );
  return lines.join("\n");
}

/** Inject a newly-checked SOP step into the 【处理措施】 section. */
function injectSopStep(text: string, step: { step: number; action: string; expected?: string }): string {
  const stepTag = `[STEP ${String(step.step).padStart(2, "0")}]`;
  if (text.includes(stepTag)) return text; // already present

  const marker = "【处理措施】";
  const nextSection = /\n【[^】]+】/;

  const markerIdx = text.indexOf(marker);
  if (markerIdx === -1) {
    return text + `\n${stepTag} ${step.action}\n  排查结果：\n`;
  }

  const afterMarker = text.indexOf("\n", markerIdx + marker.length);
  const searchFrom = afterMarker === -1 ? text.length : afterMarker + 1;
  const nextMatch = text.slice(searchFrom).search(nextSection);
  const insertAt = nextMatch === -1 ? text.length : searchFrom + nextMatch;

  const expectedHint = step.expected ? `\n  预期：${step.expected}` : "";
  const stepLine = `\n${stepTag} ${step.action}${expectedHint}\n  排查结果：\n`;
  return text.slice(0, insertAt) + stepLine + text.slice(insertAt);
}

// ── Error message mapper ──────────────────────────────────────────────────────

function toUserFriendlyError(raw: string | null | undefined): { prefix: string; message: string } {
  if (!raw) return { prefix: "[系统异常]", message: "诊断过程出现未知异常，请重试" };
  const r = raw.toLowerCase();

  if (raw.includes("reasoning failed"))
    return {
      prefix: "[AI推理]",
      message: "诊断推理节点异常，根因分析未能完成。请检查知识库是否已入库，或重新提交",
    };
  if (raw.includes("report_gen failed"))
    return {
      prefix: "[报告生成]",
      message: "报告生成节点异常，SOP 及交班草稿未能输出，根因分析结果仍可查看",
    };
  if (raw.includes("symptom_parser") || raw.includes("symptom parser"))
    return {
      prefix: "[症状解析]",
      message: "症状解析节点异常，请检查输入描述是否过短或含特殊字符",
    };
  if (r.includes("retrieval") || r.includes("chroma") || r.includes("vector"))
    return {
      prefix: "[知识检索]",
      message: "知识库检索异常，请确认已完成知识库入库（ingest.sh），或重启后端服务",
    };
  if (r.includes("json") || r.includes("parse") || r.includes("decode"))
    return {
      prefix: "[数据解析]",
      message: "AI 返回数据格式异常，已自动尝试修复。若问题持续请联系平台维护工程师",
    };
  if (r.includes("connect") || r.includes("network") || r.includes("timeout") || r.includes("refused"))
    return {
      prefix: "[网络连接]",
      message: "与 AI 服务连接中断或超时，请检查后端服务是否正常运行",
    };
  if (r.includes("api") || r.includes("anthropic") || r.includes("rate") || r.includes("quota"))
    return {
      prefix: "[API 限流]",
      message: "AI 接口调用异常（可能触发频率限制或配额不足），请稍后重试",
    };

  return {
    prefix: "[系统异常]",
    message: "诊断流程出现未预期错误，请重试或联系平台维护工程师",
  };
}

function formatErrorToast(raw: string | null | undefined, context?: string): string {
  const { prefix, message } = toUserFriendlyError(raw);
  return context ? `${prefix} ${context} — ${message}` : `${prefix} ${message}`;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const TOPIC_LABELS: Record<string, string> = {
  vibration_swing: "振动与摆度",
  governor_oil_pressure: "调速器油压",
  bearing_temp_cooling: "轴承温升",
};

const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800 critical-pulse",
};

const AUTO_ARCHIVE_DELAY = 2 * 60 * 1000;

// ── Shared helpers ────────────────────────────────────────────────────────────

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

export function SourcesPanel({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4">
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
      <img src={logoUrl} alt="logo" className="h-16 w-16 object-contain opacity-10 select-none mb-4" />
      <p className="font-display text-sm uppercase tracking-widest text-text-muted">
        诊断结果将在此展示
      </p>
      <p className="text-text-muted text-xs mt-2 max-w-xs leading-relaxed">
        在左侧选择机组、设备和异常类型，描述故障现象后点击「开始诊断」
      </p>
    </div>
  );
}

function ManualResultsPanel({ result, query }: { result: DiagnosisResult | null; query: string }) {
  const { addRecord } = useSessionHistory();
  const { addToPending } = useAutoStore();
  const [allSopChecked, setAllSopChecked] = useState(false);
  const [archivedId, setArchivedId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>(loadAllNotes);
  const prevCheckedRef = useRef<Set<number>>(new Set());

  // Reset per-session state when a new result arrives
  useEffect(() => {
    setArchivedId(null);
    setAllSopChecked(false);
    prevCheckedRef.current = new Set();
    // Pre-fill template if no existing note for this session
    if (result?.session_id) {
      setNotes((prev) => {
        if (prev[result.session_id]) return prev;
        const withTemplate = { ...prev, [result.session_id]: buildReportTemplate(result, query) };
        saveAllNotes(withTemplate);
        return withTemplate;
      });
    }
  }, [result?.session_id]); // intentionally omit `result`/`query` — only re-run on session change

  // Derive session-scoped values (safe with null result)
  const sessionId = result?.session_id ?? "";
  const noteText = notes[sessionId] ?? "";
  const isArchived = archivedId === sessionId && sessionId !== "";
  const sopRequired = (result?.check_steps.length ?? 0) > 0;
  const canSubmit = (!sopRequired || allSopChecked) && noteText.trim().length > 0 && !isArchived;

  const handleNoteChange = useCallback((val: string) => {
    if (!sessionId) return;
    setNotes((prev) => {
      const updated = { ...prev, [sessionId]: val };
      saveAllNotes(updated);
      return updated;
    });
  }, [sessionId]);

  // Inject newly-checked SOP steps into the 【处理措施】 section
  const handleCheckedChange = useCallback(
    (checked: Set<number>) => {
      if (!result) return;
      const prev = prevCheckedRef.current;
      const newlyChecked = [...checked].filter((n) => !prev.has(n));
      prevCheckedRef.current = new Set(checked);
      if (newlyChecked.length === 0) return;
      setNotes((prevNotes) => {
        let text = prevNotes[sessionId] ?? "";
        for (const stepNum of newlyChecked) {
          const step = result.check_steps.find((s) => s.step === stepNum);
          if (step) text = injectSopStep(text, step);
        }
        const updated = { ...prevNotes, [sessionId]: text };
        saveAllNotes(updated);
        return updated;
      });
    },
    [result, sessionId],
  );

  const handlePending = useCallback(() => {
    if (!result || isArchived) return;
    addToPending({
      id: sessionId,
      unit_id: result.unit_id ?? "",
      fault_types: result.topic ? [TOPIC_LABELS[result.topic] ?? result.topic] : [],
      risk_level: result.risk_level,
      root_causes: result.root_causes,
      check_steps: result.check_steps,
      report_draft: result.report_draft ?? null,
      triggered_at: new Date().toISOString(),
      archived_at: new Date().toISOString(),
      source: "manual_pending",
      completed: false,
      query,
      sources: result.sources,
    } satisfies PendingArchiveItem);
    setArchivedId(sessionId);
  }, [result, sessionId, isArchived, addToPending, query]);

  const handleSubmitArchive = useCallback(() => {
    if (!result || !canSubmit) return;
    addRecord(query || result.unit_id || sessionId, result);
    setArchivedId(sessionId);
  }, [result, canSubmit, query, sessionId, addRecord]);

  // Early return AFTER all hooks
  if (!result) return <EmptyResultPanel />;

  return (
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
      {sopRequired && (
        <section>
          <h2 className="mb-3 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
            检查操作规程 (SOP)
            <div className="flex-1 h-px bg-surface-border" />
          </h2>
          <div className="animate-result" style={{ animationDelay: "0.25s", opacity: 0 }}>
            <ChecklistPanel
              steps={result.check_steps}
              sessionId={sessionId}
              onAllChecked={setAllSopChecked}
              onCheckedChange={handleCheckedChange}
            />
          </div>
        </section>
      )}
      {result.report_draft && (
        <div className="animate-result" style={{ animationDelay: "0.3s", opacity: 0 }}>
          <ReportDraft draft={result.report_draft} sessionId={sessionId} />
        </div>
      )}
      <SourcesPanel sources={result.sources} />

      {/* ── Workflow actions ────────────────────────────────────────────────── */}
      {isArchived ? (
        <div className="rounded-lg border border-emerald-800/30 bg-emerald-950/10 p-4">
          <span className="text-xs text-emerald-400">
            ✓ 已归档，可在「历史记录」中查看
          </span>
        </div>
      ) : (
        <div className="rounded-lg border border-surface-border bg-surface-card p-4 space-y-4 animate-result" style={{ animationDelay: "0.35s", opacity: 0 }}>
          {/* Human report */}
          <div className="space-y-2">
            <p className="text-xs font-display uppercase tracking-wider text-text-muted">
              人工处理报告
            </p>
            <textarea
              value={noteText}
              onChange={(e) => handleNoteChange(e.target.value)}
              rows={8}
              className="w-full rounded-lg border border-surface-border bg-surface-elevated px-3 py-2 text-xs text-text-primary placeholder-text-muted resize-y focus:outline-none focus:border-amber/50 focus:ring-1 focus:ring-amber/30 leading-relaxed font-mono"
            />
            <p className="text-[10px] text-text-muted">内容自动保存至本地</p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <button
              onClick={handlePending}
              className="px-3 py-1.5 text-xs font-medium rounded border border-surface-border text-text-secondary hover:text-text-primary hover:border-text-secondary transition-colors"
            >
              稍后处理 →
            </button>
            <div className="flex items-center gap-3">
              {sopRequired && !allSopChecked && (
                <span className="text-xs text-text-muted">请先完成 SOP 检查清单</span>
              )}
              <button
                onClick={handleSubmitArchive}
                disabled={!canSubmit}
                className="px-4 py-2 text-sm font-medium rounded border border-emerald-700 bg-emerald-950/40 text-emerald-400 hover:bg-emerald-950/70 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                提交归档 — 故障已消缺 ✓
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Auto result panel ─────────────────────────────────────────────────────────

function AutoResultPanel() {
  const { results, selectedSessionId, setSelectedSessionId, addToPending, pendingArchive, addToast } =
    useAutoStore();

  const handledRef = useRef<Set<string>>(new Set());
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const notifiedErrorsRef = useRef<Set<string>>(new Set());

  const archiveRecord = useCallback(
    (rec: (typeof results)[number], reason: "manual" | "auto") => {
      handledRef.current.add(rec.session_id);
      const t = timersRef.current.get(rec.session_id);
      if (t) { clearTimeout(t); timersRef.current.delete(rec.session_id); }
      addToPending({
        id: rec.session_id,
        unit_id: rec.unit_id,
        fault_types: rec.fault_types,
        risk_level: rec.risk_level,
        root_causes: rec.root_causes,
        check_steps: rec.check_steps,
        report_draft: rec.report_draft,
        triggered_at: rec.triggered_at,
        archived_at: new Date().toISOString(),
        source: "auto_diagnosed",
        completed: false,
      } satisfies PendingArchiveItem);
      if (reason === "auto") {
        addToast(
          `${rec.unit_id} ${rec.fault_types[0] ?? "故障"}报告两分钟内未处理，已自动归档，可从「历史记录 → 待处理」查看。`,
        );
      }
    },
    [addToPending, addToast],
  );

  // Manage per-result timers; skip errored records entirely
  useEffect(() => {
    const viewedId = selectedSessionId ?? results[0]?.session_id;

    results.forEach((rec) => {
      // Errored records: notify once, never archive
      if (rec.error) {
        const t = timersRef.current.get(rec.session_id);
        if (t) { clearTimeout(t); timersRef.current.delete(rec.session_id); }
        if (!notifiedErrorsRef.current.has(rec.session_id)) {
          notifiedErrorsRef.current.add(rec.session_id);
          addToast(formatErrorToast(rec.error, `${rec.unit_id} ${rec.fault_types[0] ?? "自动诊断"}`));
        }
        return;
      }

      const alreadyHandled =
        handledRef.current.has(rec.session_id) ||
        pendingArchive.some((p) => p.id === rec.session_id);
      if (alreadyHandled) {
        const t = timersRef.current.get(rec.session_id);
        if (t) { clearTimeout(t); timersRef.current.delete(rec.session_id); }
        return;
      }
      if (rec.session_id === viewedId) {
        const t = timersRef.current.get(rec.session_id);
        if (t) { clearTimeout(t); timersRef.current.delete(rec.session_id); }
        return;
      }
      if (timersRef.current.has(rec.session_id)) return;
      const timer = setTimeout(() => {
        timersRef.current.delete(rec.session_id);
        archiveRecord(rec, "auto");
      }, AUTO_ARCHIVE_DELAY);
      timersRef.current.set(rec.session_id, timer);
    });

    timersRef.current.forEach((t, id) => {
      if (!results.some((r) => r.session_id === id)) {
        clearTimeout(t);
        timersRef.current.delete(id);
      }
    });
  }, [results, selectedSessionId, pendingArchive, archiveRecord, addToast]);

  useEffect(() => {
    return () => { timersRef.current.forEach((t) => clearTimeout(t)); };
  }, []);

  const record = results.find((r) => r.session_id === selectedSessionId) ?? results[0] ?? null;
  const currentPos = record ? results.findIndex((r) => r.session_id === record.session_id) : -1;

  const handlePending = () => {
    if (!record || record.error) return;
    archiveRecord(record, "manual");
    const nextRec = results.find(
      (r, i) =>
        i > currentPos &&
        !r.error &&
        !handledRef.current.has(r.session_id) &&
        !pendingArchive.some((p) => p.id === r.session_id),
    );
    if (nextRec) setSelectedSessionId(nextRec.session_id);
  };

  if (!record) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center py-20">
        <img src={logoUrl} alt="logo" className="h-16 w-16 object-contain opacity-10 select-none mb-4" />
        <p className="font-display text-sm uppercase tracking-widest text-text-muted">
          等待自动诊断结果
        </p>
        <p className="text-text-muted text-xs mt-2 max-w-xs leading-relaxed">
          传感器检测到故障后将自动触发诊断并在此展示报告
        </p>
      </div>
    );
  }

  const isArchived =
    handledRef.current.has(record.session_id) ||
    pendingArchive.some((p) => p.id === record.session_id);
  const hasError = Boolean(record.error);

  const { prefix: errPrefix, message: errMessage } = hasError
    ? toUserFriendlyError(record.error)
    : { prefix: "", message: "" };

  return (
    <div className="space-y-4">
      {/* Navigation */}
      <div className="flex items-center justify-between gap-2 rounded-lg border border-surface-border bg-surface-card px-4 py-3">
        <button
          onClick={() => { const p = results[currentPos - 1]; if (p) setSelectedSessionId(p.session_id); }}
          disabled={currentPos <= 0}
          className="px-2 py-1 text-xs rounded border border-surface-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← 上一条
        </button>
        <span className="text-xs text-text-muted text-center">
          {currentPos + 1} / {results.length}
          {results[0] && (
            <span className="ml-2 text-text-secondary">
              最新: {results[0].unit_id} {results[0].fault_types[0]}
            </span>
          )}
        </span>
        <button
          onClick={() => { const p = results[currentPos + 1]; if (p) setSelectedSessionId(p.session_id); }}
          disabled={currentPos >= results.length - 1}
          className="px-2 py-1 text-xs rounded border border-surface-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          下一条 →
        </button>
      </div>

      {/* Record info */}
      <div className={`flex flex-wrap items-center gap-2 rounded-lg border px-4 py-3 ${
        hasError ? "border-red-800/50 bg-red-950/20" : "border-surface-border bg-surface-elevated"
      }`}>
        <span className="px-2 py-0.5 rounded border border-surface-border bg-surface-card text-text-secondary text-xs">
          <span className="text-amber">◈</span> {record.unit_id}
        </span>
        <span className="px-2 py-0.5 rounded border border-amber/30 bg-amber/10 text-amber text-xs">
          {record.fault_types.join(", ")}
        </span>
        <span className="text-xs text-text-muted">
          {new Date(record.triggered_at).toLocaleString("zh-CN")}
        </span>
        {hasError ? (
          <span className="px-2 py-0.5 rounded border border-red-800 bg-red-950/30 text-red-400 text-xs font-medium">
            诊断异常
          </span>
        ) : (
          record.risk_level && (
            <span className={`px-2 py-0.5 rounded border text-xs font-semibold font-display tracking-wide ${darkRiskColors[record.risk_level]}`}>
              {record.risk_level}
            </span>
          )
        )}
        {isArchived && !hasError && (
          <span className="px-2 py-0.5 rounded border border-emerald-800 bg-emerald-950/20 text-emerald-400 text-xs">
            已归档至待处理
          </span>
        )}
        {record.escalation_required && record.escalation_reason && !hasError && (
          <span className="text-xs text-red-400">{record.escalation_reason}</span>
        )}
      </div>

      {/* Error state — shown instead of report content */}
      {hasError ? (
        <div className="rounded-lg border border-red-800/40 bg-red-950/20 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-red-400 text-base">✕</span>
            <span className="font-display text-xs uppercase tracking-wider text-red-400">
              流水线节点异常
            </span>
          </div>
          <p className="text-sm text-text-primary">
            <span className="font-mono text-red-400 mr-2">{errPrefix}</span>
            {errMessage}
          </p>
          <p className="text-xs text-text-muted leading-relaxed">
            此次诊断记录不会归档，请排查问题后重新触发诊断。若持续出现，可将错误前缀提供给平台维护工程师。
          </p>
        </div>
      ) : (
        <>
          {/* Root causes */}
          {record.root_causes.length > 0 && (
            <section>
              <h2 className="mb-3 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
                根因分析 — TOP {record.root_causes.length}
                <div className="flex-1 h-px bg-surface-border" />
              </h2>
              <div className="space-y-3">
                {record.root_causes.map((rc) => (
                  <RootCauseCard key={rc.rank} cause={rc} />
                ))}
              </div>
            </section>
          )}

          {/* Checklist */}
          {record.check_steps.length > 0 && (
            <section>
              <h2 className="mb-3 font-display text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
                检查操作规程 (SOP)
                <div className="flex-1 h-px bg-surface-border" />
              </h2>
              <ChecklistPanel steps={record.check_steps} />
            </section>
          )}

          {record.report_draft && (
            <ReportDraft draft={record.report_draft} sessionId={record.session_id} />
          )}

          <SourcesPanel sources={record.sources} />

          {/* 稍后处理 */}
          <div className="rounded-lg border border-surface-border bg-surface-card p-4 flex items-center justify-between gap-4">
            {isArchived ? (
              <span className="text-xs text-emerald-400">✓ 已归档至「历史记录 → 待处理」</span>
            ) : (
              <>
                <button
                  onClick={handlePending}
                  className="px-4 py-2 text-sm font-medium rounded border border-amber/30 bg-amber/10 text-amber hover:bg-amber/20 transition-colors"
                >
                  稍后处理 →
                </button>
                <span className="text-xs text-text-muted">
                  正在浏览 — 不会自动归档；其余未浏览报告将在 2 分钟后自动归档
                </span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function DiagnosisPage() {
  const { run, abort } = useSSEDiagnosis();
  const { phase, result, error: diagError } = useDiagnosisStore();
  const { enabled, addToast } = useAutoStore();
  const [lastQuery, setLastQuery] = useState("");

  const isManualRunning = phase !== "idle" && phase !== "done" && phase !== "error";

  // Toast on manual diagnosis errors
  useEffect(() => {
    if (phase === "error" && diagError) {
      addToast(formatErrorToast(diagError));
    }
  }, [phase, diagError, addToast]);

  const handleSubmit = useCallback(
    async (request: DiagnosisRequest) => {
      setLastQuery(request.query);
      await run(request);
    },
    [run],
  );

  return (
    <div className="flex h-[calc(100vh-52px)]">
      <aside className="w-5/12 sticky top-[52px] overflow-y-auto border-r border-surface-border p-6 space-y-4">
        {enabled ? (
          <AutoDiagnosisPanel isManualRunning={isManualRunning} />
        ) : (
          <>
            <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-amber p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="font-display text-xs uppercase tracking-widest text-text-muted">
                  故障参数输入
                </span>
                <div className="flex-1 h-px bg-surface-border" />
              </div>
              <InputPanel onSubmit={handleSubmit} onAbort={abort} isRunning={isManualRunning} />
            </div>
            <StreamingOutput />
          </>
        )}
      </aside>

      <main className="w-7/12 overflow-y-auto p-6 space-y-4">
        {enabled ? <AutoResultPanel /> : <ManualResultsPanel result={result} query={lastQuery} />}
      </main>
    </div>
  );
}
