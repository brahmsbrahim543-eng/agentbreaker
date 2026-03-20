import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type StatusVariant = "running" | "warning" | "killed" | "idle";
type IncidentVariant =
  | "semantic_loop"
  | "error_cascade"
  | "cost_spike"
  | "diminishing_returns"
  | "context_bloat";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant: StatusVariant | IncidentVariant;
  size?: "sm" | "md";
}

const variantStyles: Record<StatusVariant | IncidentVariant, string> = {
  running: "bg-accent/10 text-accent border-accent/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  killed: "bg-danger/10 text-danger border-danger/20",
  idle: "bg-white/[0.04] text-text-muted border-white/[0.06]",
  semantic_loop: "bg-purple/10 text-purple border-purple/20",
  error_cascade: "bg-danger/10 text-danger border-danger/20",
  cost_spike: "bg-warning/10 text-warning border-warning/20",
  diminishing_returns: "bg-warning/10 text-warning border-warning/20",
  context_bloat: "bg-accent/10 text-accent border-accent/20",
};

const variantLabels: Record<StatusVariant | IncidentVariant, string> = {
  running: "Running",
  warning: "Warning",
  killed: "Killed",
  idle: "Idle",
  semantic_loop: "Semantic Loop",
  error_cascade: "Error Cascade",
  cost_spike: "Cost Spike",
  diminishing_returns: "Diminishing Returns",
  context_bloat: "Context Bloat",
};

const sizeStyles = {
  sm: "text-[10px] px-1.5 py-0.5",
  md: "text-xs px-2 py-1",
};

export function Badge({
  variant,
  size = "md",
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded-md border transition-colors duration-200",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children ?? variantLabels[variant]}
    </span>
  );
}
