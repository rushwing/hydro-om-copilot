import type { RootCause } from "@/types/diagnosis";

interface RootCauseCardProps {
  cause: RootCause;
}

export function RootCauseCard({ cause }: RootCauseCardProps) {
  const pct = Math.round(cause.probability * 100);
  const rank = String(cause.rank).padStart(2, "0");

  // Block-style progress: 10 blocks
  const filled = Math.round(pct / 10);
  const progressBar = Array.from({ length: 10 }, (_, i) =>
    i < filled ? "█" : "░",
  ).join("");

  return (
    <div className="group rounded-lg border border-surface-border bg-surface-card border-l-4 border-l-amber p-4 hover:border-l-amber-glow transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-3">
          <span className="font-display text-lg font-bold text-amber leading-none">
            [{rank}]
          </span>
          <span className="font-display text-base font-semibold text-text-primary">
            {cause.title}
          </span>
        </div>
      </div>

      {/* Probability bar */}
      <div className="flex items-center gap-2 mb-3">
        <span className="font-mono text-xs text-amber tracking-wider">{progressBar}</span>
        <span className="font-display font-semibold text-amber text-sm">{pct}%</span>
      </div>

      {/* Evidence */}
      {cause.evidence.length > 0 && (
        <ul className="space-y-1 mb-3">
          {cause.evidence.map((e, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
              <span className="text-amber mt-0.5 shrink-0">▸</span>
              <span>{e}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Parameters to confirm */}
      {cause.parameters_to_confirm.length > 0 && (
        <div className="rounded border border-amber/20 bg-amber/5 px-3 py-2 text-xs">
          <span className="text-amber font-semibold">⚠ 待确认参数：</span>
          <span className="text-amber/80 ml-1">{cause.parameters_to_confirm.join("、")}</span>
        </div>
      )}
    </div>
  );
}
