import { useDiagnosisStore, type DiagnosisPhase } from "@/store/diagnosisStore";

const NODE_LABELS: Record<string, string> = {
  symptom_parser: "解析症状",
  image_agent: "截图识别",
  retrieval: "检索知识库",
  reasoning: "诊断推理",
  report_gen: "生成报告",
};

const PHASE_STEPS: DiagnosisPhase[] = [
  "symptom_parser",
  "image_agent",
  "retrieval",
  "reasoning",
  "report_gen",
];

type NodeStatus = "done" | "active" | "pending" | "skipped";

function getNodeStatus(step: DiagnosisPhase, currentPhase: DiagnosisPhase): NodeStatus {
  const steps = PHASE_STEPS;
  const stepIdx = steps.indexOf(step);
  const currentIdx = steps.indexOf(currentPhase as (typeof steps)[number]);

  if (currentPhase === "done") return "done";
  if (stepIdx < currentIdx) return "done";
  if (stepIdx === currentIdx) return "active";
  return "pending";
}

function PipelineNode({
  step,
  status,
  isLast,
}: {
  step: DiagnosisPhase;
  status: NodeStatus;
  isLast: boolean;
}) {
  const nodeColors = {
    done: "bg-amber border-amber",
    active: "bg-amber/20 border-amber node-active",
    pending: "bg-surface-elevated border-surface-border",
    skipped: "bg-surface-elevated border-surface-border opacity-40",
  };

  const labelColors = {
    done: "text-amber",
    active: "text-amber font-semibold",
    pending: "text-text-muted",
    skipped: "text-text-muted opacity-40",
  };

  const lineColor = status === "done" ? "bg-amber" : "bg-surface-border";

  return (
    <div className="flex flex-col items-center gap-1 flex-1">
      <div className="flex items-center w-full">
        {/* Node circle */}
        <div className="flex flex-col items-center flex-shrink-0">
          <div
            className={`h-3 w-3 rounded-full border-2 transition-all duration-500 ${nodeColors[status]}`}
          />
        </div>
        {/* Connecting line */}
        {!isLast && (
          <div className={`flex-1 h-px mx-1 transition-colors duration-500 ${lineColor}`} />
        )}
      </div>
      {/* Label */}
      <span className={`text-[10px] text-center leading-tight ${labelColors[status]}`}>
        {NODE_LABELS[step] ?? step}
      </span>
      {/* Status badge */}
      {status === "active" && (
        <span className="text-[9px] text-amber/70 font-display uppercase tracking-wide">
          进行中
        </span>
      )}
      {status === "done" && (
        <span className="text-[9px] text-emerald-500 font-display uppercase tracking-wide">
          完成
        </span>
      )}
    </div>
  );
}

export function StreamingOutput() {
  const { phase, streamText, error } = useDiagnosisStore();

  if (phase === "idle") return null;

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4 space-y-4">
      {/* Pipeline visualization */}
      <div>
        <p className="font-display text-xs uppercase tracking-widest text-text-muted mb-3">
          诊断流水线
        </p>
        <div className="flex items-start justify-between">
          {PHASE_STEPS.map((step, i) => (
            <PipelineNode
              key={step}
              step={step}
              status={getNodeStatus(step, phase)}
              isLast={i === PHASE_STEPS.length - 1}
            />
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Streaming text */}
      {streamText && (
        <div className="scan-line max-h-48 overflow-y-auto rounded border border-surface-border bg-surface-elevated p-3 font-mono text-xs leading-relaxed text-text-secondary whitespace-pre-wrap">
          {streamText}
          {phase !== "done" && phase !== "error" && (
            <span className="ml-0.5 inline-block h-3 w-0.5 animate-pulse bg-amber" />
          )}
        </div>
      )}
    </div>
  );
}
