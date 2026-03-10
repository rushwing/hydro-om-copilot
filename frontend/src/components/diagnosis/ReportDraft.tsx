import { useState } from "react";

interface ReportDraftProps {
  draft: string;
  sessionId?: string;
}

export function ReportDraft({ draft, sessionId }: ReportDraftProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const now = new Date().toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="rounded-lg border border-surface-border bg-surface-card overflow-hidden">
      {/* Document header */}
      <div className="border-b border-surface-border bg-surface-elevated px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-display text-sm font-semibold tracking-wide text-text-primary">
              运维诊断报告
            </p>
            <p className="text-xs text-text-muted mt-0.5">
              {now}
              {sessionId && (
                <span className="ml-2 font-mono text-text-muted opacity-60">
                  · {sessionId.slice(0, 8)}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={handleCopy}
            className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-xs font-medium transition-colors ${
              copied
                ? "border-emerald-700 bg-emerald-950 text-emerald-400"
                : "border-surface-border bg-surface-elevated text-amber hover:border-amber/50 hover:bg-amber/5"
            }`}
          >
            {copied ? "已复制 ✓" : "复制报告"}
          </button>
        </div>
      </div>

      {/* Report content */}
      <pre className="max-h-64 overflow-y-auto px-4 py-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-text-secondary">
        {draft}
      </pre>

      {/* Disclaimer */}
      <div className="border-t border-surface-border bg-surface-elevated px-4 py-2">
        <p className="text-[10px] text-text-muted">
          ⚠ 本报告由 AI 辅助生成，仅供参考，须经运维人员核实后方可作为操作依据
        </p>
      </div>
    </div>
  );
}
