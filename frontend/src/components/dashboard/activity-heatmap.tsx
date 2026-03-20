import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { HeatmapData } from "@/hooks/use-analytics";

interface ActivityHeatmapProps {
  data: HeatmapData;
}

function getIntensityClass(value: number): string {
  if (value <= 5) return "bg-white/[0.03]";
  if (value <= 20) return "bg-accent/20";
  if (value <= 40) return "bg-accent/35";
  if (value <= 60) return "bg-accent/50";
  if (value <= 80) return "bg-accent/65";
  return "bg-accent/80";
}

const DAY_LABELS = ["Mon", "", "Wed", "", "Fri", "", "Sun"];

export function ActivityHeatmap({ data }: ActivityHeatmapProps) {
  const [tooltip, setTooltip] = useState<{
    value: number;
    x: number;
    y: number;
    label: string;
  } | null>(null);

  const rows = data.data; // 7 rows (days) x N cols (weeks)
  const colLabels = data.labels_x;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="relative"
    >
      {/* Column labels (weeks/months) */}
      <div className="flex ml-10 mb-2 gap-[3px]">
        {colLabels.map((label, i) => (
          <div
            key={i}
            className="text-[10px] text-text-muted font-medium"
            style={{ width: 12, textAlign: "center" }}
          >
            {i % 2 === 0 ? label.split(" ")[0] : ""}
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="flex gap-0">
        {/* Row labels (days) */}
        <div className="flex flex-col gap-[3px] mr-2 pt-[1px]">
          {DAY_LABELS.map((label, i) => (
            <div
              key={i}
              className="h-3 flex items-center justify-end text-[10px] text-text-muted font-medium pr-1"
              style={{ width: 32 }}
            >
              {label}
            </div>
          ))}
        </div>

        {/* Cells */}
        <div className="flex flex-col gap-[3px]">
          {rows.map((row, rowIdx) => (
            <div key={rowIdx} className="flex gap-[3px]">
              {row.map((value, colIdx) => (
                <div
                  key={colIdx}
                  className={cn(
                    "w-3 h-3 rounded-[3px] transition-all duration-200 cursor-pointer",
                    "hover:ring-1 hover:ring-accent/40 hover:scale-125",
                    getIntensityClass(value)
                  )}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setTooltip({
                      value,
                      x: rect.left + rect.width / 2,
                      y: rect.top - 8,
                      label: `${data.labels_y[rowIdx]}, ${colLabels[colIdx]}`,
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
          }}
        >
          <div className="bg-surface border border-border rounded-md px-2.5 py-1.5 shadow-xl">
            <p className="text-[10px] text-text-muted">{tooltip.label}</p>
            <p className="text-xs font-mono font-bold text-accent">
              {tooltip.value} events
            </p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-2 mt-4 ml-10">
        <span className="text-[10px] text-text-muted">Less</span>
        {[3, 20, 40, 60, 80].map((v) => (
          <div
            key={v}
            className={cn("w-3 h-3 rounded-[3px]", getIntensityClass(v))}
          />
        ))}
        <span className="text-[10px] text-text-muted">More</span>
      </div>
    </motion.div>
  );
}
