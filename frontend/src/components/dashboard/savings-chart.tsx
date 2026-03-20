import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  type TooltipProps,
} from "recharts";
import type { TimelinePoint } from "@/hooks/use-analytics";

interface SavingsChartProps {
  data: TimelinePoint[];
}

function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatEuro(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(0)}K €`;
  return `${value.toLocaleString("fr-FR")} €`;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const val = payload[0].value as number;

  return (
    <div className="bg-surface border border-border rounded-lg px-4 py-3 shadow-xl">
      <p className="text-xs text-text-muted mb-1">
        {formatAxisDate(label ?? "")}
      </p>
      <p className="text-sm font-mono font-bold text-accent">
        {val.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
      </p>
      <p className="text-[10px] text-text-muted mt-0.5">cost saved</p>
    </div>
  );
}

export function SavingsChart({ data }: SavingsChartProps) {
  // Only show every ~5th tick to avoid clutter
  const ticks = useMemo(() => {
    const step = Math.max(1, Math.floor(data.length / 6));
    return data.filter((_, i) => i % step === 0).map((d) => d.date);
  }, [data]);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart
        data={data}
        margin={{ top: 8, right: 8, left: -10, bottom: 0 }}
      >
        <defs>
          <linearGradient id="savingsGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00D4FF" stopOpacity={0.3} />
            <stop offset="50%" stopColor="#00D4FF" stopOpacity={0.08} />
            <stop offset="100%" stopColor="#00D4FF" stopOpacity={0} />
          </linearGradient>
        </defs>

        <XAxis
          dataKey="date"
          axisLine={false}
          tickLine={false}
          tick={{ fill: "#8B8B9E", fontSize: 11, fontFamily: "Inter" }}
          tickFormatter={formatAxisDate}
          ticks={ticks}
          dy={8}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: "#8B8B9E", fontSize: 11, fontFamily: "JetBrains Mono" }}
          tickFormatter={formatEuro}
          width={55}
        />
        <Tooltip
          content={<CustomTooltip />}
          cursor={{
            stroke: "rgba(0, 212, 255, 0.15)",
            strokeWidth: 1,
            strokeDasharray: "4 4",
          }}
        />
        <Area
          type="monotone"
          dataKey="cost_saved"
          stroke="#00D4FF"
          strokeWidth={2}
          fill="url(#savingsGradient)"
          animationDuration={1500}
          animationEasing="ease-out"
          dot={false}
          activeDot={{
            r: 4,
            fill: "#00D4FF",
            stroke: "#0A0A0F",
            strokeWidth: 2,
          }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
