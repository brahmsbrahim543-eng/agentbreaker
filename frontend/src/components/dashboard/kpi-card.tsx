import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

type ColorKey = "accent" | "success" | "danger" | "warning";

interface KpiCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  color: ColorKey;
  trend?: string;
  trendColor?: ColorKey;
  prefix?: string;
}

const colorMap: Record<ColorKey, { bg: string; text: string; glow: string }> = {
  accent: {
    bg: "bg-accent-dim",
    text: "text-accent",
    glow: "shadow-[0_0_20px_-4px_rgba(0,212,255,0.25)]",
  },
  success: {
    bg: "bg-success-dim",
    text: "text-success",
    glow: "shadow-[0_0_20px_-4px_rgba(16,185,129,0.25)]",
  },
  danger: {
    bg: "bg-danger-dim",
    text: "text-danger",
    glow: "shadow-[0_0_20px_-4px_rgba(239,68,68,0.25)]",
  },
  warning: {
    bg: "bg-warning-dim",
    text: "text-warning",
    glow: "shadow-[0_0_20px_-4px_rgba(245,158,11,0.25)]",
  },
};

export function KpiCard({
  title,
  value,
  icon: Icon,
  color,
  trend,
  trendColor,
  prefix,
}: KpiCardProps) {
  const c = colorMap[color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={cn(
        "group relative bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-xl p-6",
        "hover:border-white/[0.12] hover:bg-white/[0.05] transition-all duration-300",
        "overflow-hidden"
      )}
    >
      {/* Subtle glow on hover */}
      <div
        className={cn(
          "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-xl",
          c.glow
        )}
      />

      <div className="relative z-10 flex items-start justify-between">
        <div className="space-y-3">
          <div
            className={cn(
              "inline-flex items-center justify-center w-10 h-10 rounded-lg",
              c.bg
            )}
          >
            <Icon className={cn("w-5 h-5", c.text)} strokeWidth={1.8} />
          </div>

          <div>
            <p className="text-sm text-text-muted font-medium tracking-wide">
              {title}
            </p>
            <p className={cn("text-2xl font-bold font-mono mt-1", c.text)}>
              {prefix}
              {value}
            </p>
          </div>
        </div>

        {trend && (
          <span
            className={cn(
              "text-xs font-medium font-mono px-2 py-1 rounded-md",
              trendColor
                ? cn(colorMap[trendColor].text, colorMap[trendColor].bg)
                : trend.startsWith("+") || trend.startsWith("↑")
                  ? "text-success bg-success-dim"
                  : trend.startsWith("-") || trend.startsWith("↓")
                    ? "text-danger bg-danger-dim"
                    : "text-text-muted bg-white/[0.05]"
            )}
          >
            {trend}
          </span>
        )}
      </div>

      {/* Bottom accent line */}
      <div
        className={cn(
          "absolute bottom-0 left-0 right-0 h-[1px]",
          "bg-gradient-to-r from-transparent via-current to-transparent opacity-0 group-hover:opacity-30 transition-opacity duration-500",
          c.text
        )}
      />
    </motion.div>
  );
}
