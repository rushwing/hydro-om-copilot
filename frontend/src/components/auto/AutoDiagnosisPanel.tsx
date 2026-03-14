import { useAutoStore } from "@/store/autoStore";
import { useAutoDiagnosis } from "@/hooks/useAutoDiagnosis";
import type {
  AutoDiagnosisStatus,
  CurrentDiagnosisInfo,
  EpochPhase,
  PendingFaultItem,
  SensorPointSnapshot,
} from "@/types/diagnosis";

// ── Constants ────────────────────────────────────────────────────────────────

const AUTO_PHASE_STEPS = [
  "sensor_reader",
  "symptom_parser",
  "image_agent",
  "retrieval",
  "reasoning",
  "report_gen",
] as const;

const AUTO_NODE_LABELS: Record<string, string> = {
  sensor_reader: "传感器探测",
  symptom_parser: "解析症状",
  image_agent: "截图识别",
  retrieval: "检索知识库",
  reasoning: "诊断推理",
  report_gen: "生成报告",
};

const EPOCH_COLORS: Record<EpochPhase, { bar: string; text: string; bg: string }> = {
  NORMAL: { bar: "bg-emerald-500", text: "text-emerald-400", bg: "bg-emerald-950 border-emerald-800" },
  PRE_FAULT: { bar: "bg-amber-500", text: "text-amber", bg: "bg-amber-950 border-amber-800" },
  FAULT: { bar: "bg-red-500", text: "text-red-400", bg: "bg-red-950 border-red-800" },
  COOL_DOWN: { bar: "bg-blue-500", text: "text-blue-400", bg: "bg-blue-950 border-blue-800" },
};

const EPOCH_LABELS: Record<EpochPhase, string> = {
  NORMAL: "正常",
  PRE_FAULT: "预警",
  FAULT: "故障",
  COOL_DOWN: "冷却",
};

const ALARM_COLORS: Record<string, string> = {
  normal: "text-emerald-400",
  warn: "text-amber",
  alarm: "text-orange-400",
  trip: "text-red-400",
};

const PHASE_PROGRESS: Record<string, number> = {
  sensor_reader: 16,
  symptom_parser: 33,
  image_agent: 50,
  retrieval: 66,
  reasoning: 83,
  report_gen: 95,
  done: 100,
  error: 0,
};

function getProgressColor(pct: number): string {
  if (pct <= 33) return "bg-red-500";
  if (pct <= 50) return "bg-orange-500";
  if (pct <= 66) return "bg-amber-500";
  if (pct <= 83) return "bg-yellow-500";
  return "bg-emerald-500";
}

function relativeTime(isoStr: string): string {
  const elapsed = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  return `${elapsed}s 前`;
}

// ── Sub-components ───────────────────────────────────────────────────────────

function SimulatedDataBanner() {
  return (
    <div className="rounded border border-amber/30 bg-amber/10 px-3 py-2 text-xs text-amber flex items-center gap-2">
      <span>⚠</span>
      <span>当前数据来源：随机故障模拟引擎，非真实电厂采集</span>
    </div>
  );
}

function EpochIndicator({ status }: { status: AutoDiagnosisStatus }) {
  const { epoch_num, epoch_elapsed_s, epoch_phase } = status;
  const colors = EPOCH_COLORS[epoch_phase];
  const pct = Math.round((epoch_elapsed_s / 300) * 100);
  const phases: EpochPhase[] = ["NORMAL", "PRE_FAULT", "FAULT", "COOL_DOWN"];

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-display text-xs uppercase tracking-wider text-text-muted">
          传感器采集周期（模拟）
        </span>
        <span className="font-mono text-xs text-text-secondary">
          EPOCH #{epoch_num} · {epoch_elapsed_s}/300s
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${colors.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Phase pills */}
      <div className="flex gap-2">
        {phases.map((p) => {
          const isActive = p === epoch_phase;
          const c = EPOCH_COLORS[p];
          return (
            <span
              key={p}
              className={`flex-1 text-center rounded border px-1 py-0.5 text-xs font-medium transition-all ${
                isActive
                  ? `${c.text} ${c.bg} ${p === "FAULT" ? "animate-pulse" : ""}`
                  : "text-text-muted border-surface-border bg-surface-elevated"
              }`}
            >
              {EPOCH_LABELS[p]}
              {isActive && " ●"}
            </span>
          );
        })}
      </div>
    </div>
  );
}

interface UnitStatusGridProps {
  cooldowns: Record<string, number>;
  pendingQueue: PendingFaultItem[];
  current: CurrentDiagnosisInfo | null;
  epochNum: number;
}

function UnitStatusGrid({ cooldowns, pendingQueue, current, epochNum }: UnitStatusGridProps) {
  const units = ["#1机", "#2机", "#3机", "#4机"];
  // Units with a fault waiting in queue
  const faultUnits = new Set(pendingQueue.map((f) => f.unit_id));
  // Unit actively being diagnosed also counts as a red / unresolved fault state
  const diagnosingUnit = current?.unit_id ?? null;
  // Before any epoch completes, show neutral state for all units
  const hasData = epochNum > 0;

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4">
      <h3 className="font-display text-xs uppercase tracking-wider text-text-muted mb-1">
        各机组故障状态
      </h3>
      <p className="text-xs text-text-muted mb-3">
        {hasData ? "红色：存在待处理故障；绿色：暂无故障" : "首轮采集尚未完成，等待数据…"}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {units.map((uid) => {
          const hasFault = faultUnits.has(uid);
          const isDiagnosing = diagnosingUnit === uid;
          const isRed = hasFault || isDiagnosing;
          const cooling = (cooldowns[uid] ?? 0) > 0;
          return (
            <div
              key={uid}
              className={`rounded border px-3 py-2 flex items-center justify-between text-xs ${
                !hasData
                  ? "border-surface-border bg-surface-elevated text-text-muted"
                  : isRed
                  ? "border-red-800 bg-red-950/30 text-red-400"
                  : "border-emerald-800 bg-emerald-950/30 text-emerald-400"
              }`}
            >
              <span className="font-medium">{uid}</span>
              {!hasData ? (
                <span className="text-text-muted">—</span>
              ) : isDiagnosing ? (
                <span className="text-red-400 animate-pulse">⟳ 诊断中</span>
              ) : hasFault ? (
                <span className="text-red-400">⚠ 待处理</span>
              ) : cooling ? (
                <span className="font-mono text-text-secondary">⏱ {cooldowns[uid]}s</span>
              ) : (
                <span className="text-emerald-400">✓ 正常</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface FaultQueueListProps {
  queue: PendingFaultItem[];
}

function FaultQueueList({ queue }: FaultQueueListProps) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4">
      <h3 className="font-display text-xs uppercase tracking-wider text-text-muted mb-3 flex items-center gap-2">
        待处理故障
        <span className="px-1.5 py-0.5 rounded bg-amber/10 border border-amber/30 text-amber text-xs">
          {queue.length}
        </span>
      </h3>
      {queue.length === 0 ? (
        <p className="text-text-muted text-xs">暂无待处理故障</p>
      ) : (
        <div className="space-y-2">
          {queue.map((item, i) => {
            const isFirst = i === 0;
            const isLast = i === queue.length - 1;
            return (
              <div
                key={`${item.unit_id}-${item.queued_at}-${i}`}
                className={`rounded border px-3 py-2 text-xs ${
                  isFirst
                    ? "border-amber/30 bg-amber/10"
                    : "border-surface-border bg-surface-elevated"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {isFirst && (
                    <span className="text-amber font-bold text-xs px-1 rounded bg-amber/20">
                      最新
                    </span>
                  )}
                  {isLast && !isFirst && (
                    <span className="text-text-muted font-bold text-xs px-1 rounded bg-surface-border">
                      最旧
                    </span>
                  )}
                  <span className="font-medium text-text-primary">{item.unit_id}</span>
                  <span className="text-text-muted">—</span>
                  <span className="text-text-secondary">{item.fault_types.join(", ")}</span>
                  <span className="ml-auto text-text-muted font-mono">
                    {relativeTime(item.queued_at)}
                  </span>
                </div>
                <p className="text-text-muted leading-relaxed truncate">{item.symptom_preview}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AutoPipelineView({ phase }: { phase: string }) {
  const isDone = phase === "done";
  const isError = phase === "error";

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {AUTO_PHASE_STEPS.map((step, i) => {
        const label = AUTO_NODE_LABELS[step];
        const isActive = phase === step;
        const isPast =
          !isDone &&
          !isError &&
          AUTO_PHASE_STEPS.indexOf(step) < AUTO_PHASE_STEPS.indexOf(phase as typeof AUTO_PHASE_STEPS[number]);
        const isCompleted = isDone || isPast;

        return (
          <div key={step} className="flex items-center gap-1">
            <span
              className={`px-2 py-0.5 rounded text-xs border transition-all ${
                isActive
                  ? "border-amber/50 bg-amber/20 text-amber font-medium animate-pulse"
                  : isCompleted
                  ? "border-emerald-800 bg-emerald-950/30 text-emerald-400"
                  : isError && (step as string) === phase
                  ? "border-red-800 bg-red-950/30 text-red-400"
                  : "border-surface-border bg-surface-elevated text-text-muted"
              }`}
            >
              {label}
            </span>
            {i < AUTO_PHASE_STEPS.length - 1 && (
              <span className="text-text-muted text-xs">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SensorDataTable({ data }: { data: SensorPointSnapshot[] }) {
  if (data.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-muted border-b border-surface-border">
            <th className="text-left py-1 pr-3 font-medium">测点</th>
            <th className="text-right py-1 pr-3 font-medium">数值</th>
            <th className="text-left py-1 pr-3 font-medium">状态</th>
            <th className="text-left py-1 font-medium">趋势</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {data.map((pt) => (
            <tr key={pt.tag} className="font-mono">
              <td className="py-1 pr-3 text-text-secondary">{pt.name_cn}</td>
              <td className="py-1 pr-3 text-right text-text-primary">
                {pt.value.toFixed(3)}{pt.thresholds.unit as string}
              </td>
              <td className={`py-1 pr-3 uppercase font-bold ${ALARM_COLORS[pt.alarm_state] ?? "text-text-muted"}`}>
                {pt.alarm_state}
              </td>
              <td className="py-1 text-text-muted">{pt.trend}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CurrentDiagnosisCard({ current }: { current: CurrentDiagnosisInfo }) {
  const pct = PHASE_PROGRESS[current.phase] ?? 0;
  const progressColor = getProgressColor(pct);

  return (
    <div className="rounded-lg border border-amber/30 bg-surface-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="font-display text-xs uppercase tracking-wider text-text-muted">
          当前诊断
        </span>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-text-secondary font-medium">{current.unit_id}</span>
          <span className="text-text-muted">·</span>
          <span className="text-text-muted">{current.fault_types.join(", ")}</span>
          <span className="text-text-muted">·</span>
          <span className="font-mono text-text-muted">{relativeTime(current.started_at)}</span>
        </div>
      </div>

      <AutoPipelineView phase={current.phase} />

      {/* Phase progress bar */}
      <div className="h-1.5 rounded-full bg-surface-elevated overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${progressColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {current.sensor_data.length > 0 && (
        <div>
          <p className="text-xs text-text-muted mb-2 font-medium">传感器异常测点</p>
          <SensorDataTable data={current.sensor_data} />
        </div>
      )}

      {current.stream_preview && (
        <div>
          <p className="text-xs text-text-muted mb-1 font-medium">推理输出预览</p>
          <pre className="font-mono text-xs text-text-secondary bg-surface-elevated rounded p-3 max-h-32 overflow-y-auto whitespace-pre-wrap leading-relaxed">
            {current.stream_preview}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main Panel ───────────────────────────────────────────────────────────────

interface AutoDiagnosisPanelProps {
  isManualRunning?: boolean;
}

export function AutoDiagnosisPanel({ isManualRunning = false }: AutoDiagnosisPanelProps) {
  const { enabled, status, results, setSelectedSessionId } = useAutoStore();
  const { start, stop } = useAutoDiagnosis();

  const isRunning = status?.running ?? false;
  const completedCount = status?.completed_count ?? 0;

  return (
    <div className="space-y-4">
      {/* Header card with toggle */}
      <div className="rounded-lg border border-surface-border bg-surface-card border-l-2 border-l-amber p-5">
        <div className="mb-4 flex items-center justify-between">
          <span className="font-display text-xs uppercase tracking-widest text-text-muted">
            自动诊断模式
          </span>
          <div className="flex items-center gap-3">
            {completedCount > 0 && (
              <span className="text-xs text-text-muted">
                已完成 {completedCount} 次
              </span>
            )}
            {isRunning ? (
              <button
                onClick={stop}
                disabled={isManualRunning}
                className="px-3 py-1.5 text-xs font-medium rounded border border-red-800/50 bg-red-950/30 text-red-400 hover:bg-red-950/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                停止轮询
              </button>
            ) : (
              <button
                onClick={start}
                disabled={isManualRunning || enabled}
                className="px-3 py-1.5 text-xs font-medium rounded border border-emerald-800/50 bg-emerald-950/30 text-emerald-400 hover:bg-emerald-950/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {enabled ? "等待故障..." : "启动轮询"}
              </button>
            )}
          </div>
        </div>

        <SimulatedDataBanner />
      </div>

      {status && (
        <>
          <UnitStatusGrid
            cooldowns={status.unit_cooldowns}
            pendingQueue={status.pending_queue}
            current={status.current}
            epochNum={status.epoch_num}
          />
          <EpochIndicator status={status} />
          {status.pending_queue.length > 0 && (
            <FaultQueueList queue={status.pending_queue} />
          )}
          {status.current && <CurrentDiagnosisCard current={status.current} />}
        </>
      )}

      {/* Results summary */}
      {results.length > 0 && (
        <div className="rounded-lg border border-surface-border bg-surface-card p-4">
          <h3 className="font-display text-xs uppercase tracking-wider text-text-muted mb-3">
            最近诊断结果
          </h3>
          <div className="space-y-2">
            {results.slice(0, 5).map((rec) => (
              <div
                key={rec.session_id}
                onClick={() => setSelectedSessionId(rec.session_id)}
                className="rounded border border-surface-border bg-surface-elevated px-3 py-2 text-xs flex items-center justify-between gap-2 cursor-pointer hover:border-amber/30 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-medium text-text-primary">{rec.unit_id}</span>
                  <span className="text-text-muted truncate">{rec.fault_types.join(", ")}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {rec.risk_level && (
                    <span
                      className={`px-1.5 py-0.5 rounded border text-xs font-medium ${
                        rec.risk_level === "critical"
                          ? "text-red-400 bg-red-950 border-red-800"
                          : rec.risk_level === "high"
                          ? "text-orange-400 bg-orange-950 border-orange-800"
                          : rec.risk_level === "medium"
                          ? "text-amber bg-amber-950 border-amber-800"
                          : "text-emerald-400 bg-emerald-950 border-emerald-800"
                      }`}
                    >
                      {rec.risk_level}
                    </span>
                  )}
                  {rec.error && <span className="text-red-400">ERR</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
