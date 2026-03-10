import { riskLevelLabel } from "@/store/diagnosisStore";
import type { RiskLevel } from "@/types/diagnosis";

interface RiskBadgeProps {
  level: RiskLevel;
  escalation?: boolean;
}

// Local dark-theme risk colors (store exports light-theme classes)
const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800 critical-pulse",
};

const riskIcons: Record<RiskLevel, string> = {
  low: "●",
  medium: "▲",
  high: "▲",
  critical: "⬥",
};

export function RiskBadge({ level, escalation }: RiskBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex items-center gap-1.5 rounded border px-3 py-1 text-sm font-semibold font-display tracking-wide ${darkRiskColors[level]}`}
      >
        <span className="text-xs">{riskIcons[level]}</span>
        {riskLevelLabel[level]}
      </span>
      {escalation && (
        <span className="flex items-center gap-1 rounded border border-red-800 bg-red-950 px-3 py-1 text-sm font-semibold text-red-400">
          <span>▲</span> 需升级处理
        </span>
      )}
    </div>
  );
}
