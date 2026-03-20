import { useNavigate } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn, formatRelativeTime } from "../../lib/utils";
import type { Incident } from "../../hooks/use-incidents";

interface IncidentsListProps {
  incidents: Incident[];
  loading: boolean;
}

export function IncidentsList({ incidents, loading }: IncidentsListProps) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-5 animate-pulse">
            <div className="flex items-center gap-4">
              <div className="w-20 h-6 rounded bg-white/[0.06]" />
              <div className="flex-1 h-4 bg-white/[0.04] rounded" />
              <div className="w-16 h-5 bg-white/[0.06] rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (incidents.length === 0) {
    return (
      <div className="text-center py-16">
        <AlertTriangle className="w-10 h-10 text-text-muted/30 mx-auto mb-3" />
        <p className="text-sm text-text-muted">No incidents found</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {incidents.map((incident) => (
        <div
          key={incident.id}
          onClick={() => navigate(`/incidents/${incident.id}`)}
          className={cn(
            "bg-white/[0.02] border border-white/[0.06] rounded-xl px-4 py-3 cursor-pointer",
            "hover:bg-white/[0.04] hover:border-white/[0.1]",
            "transition-all duration-200"
          )}
        >
          {/* Row 1: badge + agent name + amount + time */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Badge variant={incident.incident_type} size="sm" className="flex-shrink-0" />
              <span className="text-sm font-mono text-text-primary truncate">
                {incident.agent_name}
              </span>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className="text-sm font-mono font-semibold text-success whitespace-nowrap">
                {incident.cost_avoided.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
              </span>
              <span className="text-[11px] text-text-muted whitespace-nowrap">
                {formatRelativeTime(incident.created_at)}
              </span>
            </div>
          </div>
          {/* Row 2: score + steps */}
          <div className="mt-1 text-xs text-text-muted">
            Score{" "}
            <span className={cn("font-mono font-semibold", incident.risk_score_at_kill >= 75 ? "text-danger" : "text-warning")}>
              {Math.round(incident.risk_score_at_kill)}
            </span>
            {" · "}
            {incident.steps_before_kill} steps
          </div>
        </div>
      ))}
    </div>
  );
}
