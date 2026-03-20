import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Download, ShieldOff, DollarSign, Leaf, AlertTriangle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useIncident } from "../hooks/use-incidents";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { cn, formatRelativeTime } from "../lib/utils";

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ value: number }> }) {
  if (!active || !payload?.length) return null;
  const score = payload[0].value;
  return (
    <div className="bg-surface border border-white/[0.1] rounded-lg px-3 py-2 shadow-xl">
      <span className={cn(
        "text-sm font-mono font-semibold",
        score < 50 ? "text-success" : score < 75 ? "text-warning" : "text-danger"
      )}>
        Risk: {score}
      </span>
    </div>
  );
}

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { incident, loading } = useIncident(id!);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="text-center py-16 text-text-muted">Incident not found</div>
    );
  }

  // Build risk timeline from snapshot steps
  const riskTimeline = [...incident.snapshot_steps]
    .reverse()
    .map((step) => ({
      step: `#${step.step_number}`,
      score: step.risk_score,
    }));

  function handleExportJSON() {
    const blob = new Blob([JSON.stringify(incident, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `incident-${incident!.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate("/incidents")}
          className="mt-1 p-2 rounded-lg border border-white/[0.06] text-text-muted hover:text-text-primary hover:bg-white/[0.04] transition-all duration-150"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <Badge variant={incident.incident_type} size="md" />
            <span className="text-xs text-text-muted font-mono">{incident.id}</span>
          </div>
          <h1 className="text-xl font-semibold text-text-primary font-mono">{incident.agent_name}</h1>
          <p className="text-sm text-text-muted mt-1">
            {formatRelativeTime(incident.created_at)} &middot; Risk score{" "}
            <span className={cn(
              "font-mono font-semibold",
              incident.risk_score_at_kill >= 75 ? "text-danger" : "text-warning"
            )}>
              {incident.risk_score_at_kill}
            </span>
            {" "}&middot; {incident.steps_before_kill} steps
          </p>
        </div>
        <button
          onClick={handleExportJSON}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-white/[0.06] text-sm text-text-muted hover:text-text-primary hover:bg-white/[0.04] transition-all duration-150"
        >
          <Download className="w-4 h-4" />
          Export JSON
        </button>
      </div>

      {/* Impact Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-[11px] text-text-muted uppercase tracking-wider">Cost Avoided</p>
              <p className="text-2xl font-bold font-mono text-success">
                {incident.cost_avoided.toFixed(2).replace('.', ',')} €
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
              <Leaf className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-[11px] text-text-muted uppercase tracking-wider">CO2 Avoided</p>
              <p className="text-2xl font-bold font-mono text-success">
                {incident.co2_avoided.toFixed(1)}g
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* What Happened */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldOff className="w-4 h-4 text-danger" />
            <CardTitle>What Happened</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-primary/80 leading-relaxed">
            {incident.kill_reason_detail}
          </p>
        </CardContent>
      </Card>

      {/* Risk Timeline Mini Chart */}
      {riskTimeline.length > 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Risk Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={riskTimeline} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <ReferenceLine y={75} stroke="rgba(239,68,68,0.3)" strokeDasharray="6 3" />
                  <ReferenceLine y={50} stroke="rgba(245,158,11,0.3)" strokeDasharray="6 3" />
                  <XAxis
                    dataKey="step"
                    tick={{ fill: "#8B8B9E", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "#8B8B9E", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                    tickLine={false}
                    width={30}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#EF4444"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#EF4444", stroke: "#0A0A0F", strokeWidth: 2 }}
                    activeDot={{ r: 5, fill: "#EF4444", stroke: "#0A0A0F", strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Snapshot Steps */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <CardTitle>Snapshot &mdash; Why the Agent Was Killed</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            {incident.snapshot_steps.map((step) => (
              <div
                key={step.step_number}
                className={cn(
                  "relative flex items-start gap-4 p-3 rounded-lg transition-colors duration-150",
                  step.is_duplicate
                    ? "bg-warning/[0.04] border-l-2 border-l-warning/60"
                    : "hover:bg-white/[0.02]"
                )}
              >
                {/* Step number */}
                <div className={cn(
                  "flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center",
                  step.is_duplicate ? "bg-warning/10" : "bg-white/[0.04]"
                )}>
                  <span className={cn(
                    "text-xs font-mono",
                    step.is_duplicate ? "text-warning" : "text-text-muted"
                  )}>
                    #{step.step_number}
                  </span>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-1">
                  <p className="text-sm text-text-primary">
                    <span className="text-text-muted text-xs mr-1">IN:</span>
                    {step.input.length > 100 ? step.input.slice(0, 100) + "..." : step.input}
                  </p>
                  <p className={cn(
                    "text-sm",
                    step.is_duplicate ? "text-warning/80" : "text-text-muted"
                  )}>
                    <span className="text-text-muted/60 text-xs mr-1">OUT:</span>
                    {step.output.length > 140 ? step.output.slice(0, 140) + "..." : step.output}
                  </p>
                  {step.is_duplicate && (
                    <div className="flex items-center gap-1 mt-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse" />
                      <span className="text-[10px] text-warning/70 uppercase tracking-wider font-medium">
                        Duplicate / Loop Detected
                      </span>
                    </div>
                  )}
                </div>

                {/* Tool + Risk */}
                <div className="flex-shrink-0 text-right space-y-1">
                  {step.tool && (
                    <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.04] text-text-muted border border-white/[0.06]">
                      {step.tool}
                    </span>
                  )}
                  <p className={cn(
                    "text-xs font-mono font-semibold",
                    step.risk_score >= 75 ? "text-danger" : step.risk_score >= 50 ? "text-warning" : "text-success"
                  )}>
                    {step.risk_score}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-4 pt-4 border-t border-white/[0.06] flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm border-l-2 border-l-warning/60 bg-warning/[0.04]" />
              <span className="text-[10px] text-text-muted uppercase tracking-wider">Duplicate / Looping output</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-white/[0.04]" />
              <span className="text-[10px] text-text-muted uppercase tracking-wider">Normal step</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
