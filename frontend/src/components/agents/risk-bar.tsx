import { cn } from "../../lib/utils";

interface RiskBarProps {
  score: number;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

function getRiskColor(score: number): string {
  if (score < 50) return "bg-success";
  if (score < 75) return "bg-warning";
  return "bg-danger";
}

function getRiskGlow(score: number): string {
  if (score < 50) return "shadow-[0_0_8px_rgba(16,185,129,0.4)]";
  if (score < 75) return "shadow-[0_0_8px_rgba(245,158,11,0.4)]";
  return "shadow-[0_0_8px_rgba(239,68,68,0.5)]";
}

function getRiskTextColor(score: number): string {
  if (score < 50) return "text-success";
  if (score < 75) return "text-warning";
  return "text-danger";
}

export function RiskBar({ score, size = "sm", showLabel = true, className }: RiskBarProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const barHeight = size === "sm" ? "h-1.5" : "h-2.5";

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className={cn("flex-1 rounded-full bg-white/[0.06] overflow-hidden", barHeight)}>
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700 ease-out",
            getRiskColor(clamped),
            clamped >= 75 && getRiskGlow(clamped)
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span
          className={cn(
            "text-xs font-mono font-semibold tabular-nums min-w-[2rem] text-right",
            getRiskTextColor(clamped)
          )}
        >
          {clamped}
        </span>
      )}
    </div>
  );
}

export function RiskGauge({ score, className }: { score: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div className={cn("flex flex-col items-center gap-1", className)}>
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
          <circle
            cx="40"
            cy="40"
            r="34"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="6"
          />
          <circle
            cx="40"
            cy="40"
            r="34"
            fill="none"
            stroke={clamped < 50 ? "#10B981" : clamped < 75 ? "#F59E0B" : "#EF4444"}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${(clamped / 100) * 213.6} 213.6`}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("text-xl font-bold font-mono", getRiskTextColor(clamped))}>
            {clamped}
          </span>
        </div>
      </div>
      <span className="text-[10px] uppercase tracking-widest text-text-muted">Risk Score</span>
    </div>
  );
}
