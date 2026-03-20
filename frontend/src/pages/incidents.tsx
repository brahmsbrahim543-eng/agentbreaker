import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { Card } from "../components/ui/card";
import { IncidentsList } from "../components/incidents/incidents-list";
import { useIncidents, type IncidentType } from "../hooks/use-incidents";
import { cn } from "../lib/utils";

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All Types" },
  { value: "semantic_loop", label: "Semantic Loop" },
  { value: "error_cascade", label: "Error Cascade" },
  { value: "cost_spike", label: "Cost Spike" },
  { value: "diminishing_returns", label: "Diminishing Returns" },
  { value: "context_bloat", label: "Context Bloat" },
];

export default function IncidentsPage() {
  const [typeFilter, setTypeFilter] = useState<string>("");

  const { incidents, total, loading } = useIncidents({
    type: (typeFilter || undefined) as IncidentType | undefined,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-danger/10 border border-danger/20 flex items-center justify-center">
          <ShieldAlert className="w-5 h-5 text-danger" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Incidents</h1>
          <p className="text-sm text-text-muted">
            {total} incident{total !== 1 ? "s" : ""} detected and mitigated
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        {/* Type filter pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTypeFilter(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-200",
                typeFilter === opt.value
                  ? "bg-accent/10 text-accent border-accent/20"
                  : "bg-white/[0.02] text-text-muted border-white/[0.06] hover:bg-white/[0.04] hover:text-text-primary"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Incidents List */}
      <Card className="p-5">
        <IncidentsList incidents={incidents} loading={loading} />
      </Card>
    </div>
  );
}
