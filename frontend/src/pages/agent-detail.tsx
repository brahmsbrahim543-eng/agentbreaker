import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Terminal, DollarSign, Zap, Clock } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import { useAgent } from "../hooks/use-agents";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { RiskGauge } from "../components/agents/risk-bar";
import { cn, formatRelativeTime } from "../lib/utils";

// Generate mock risk-over-time data
function generateRiskTimeline(currentScore: number) {
  const points = 24;
  const data = [];
  let score = Math.max(5, currentScore - 30 - Math.random() * 20);
  for (let i = 0; i < points; i++) {
    const drift = (Math.random() - 0.4) * 8;
    score = Math.max(0, Math.min(100, score + drift + (currentScore - score) * 0.08));
    data.push({
      time: `${points - i}h ago`,
      score: Math.round(score),
    });
  }
  data.push({ time: "now", score: currentScore });
  return data;
}

const toolColors: Record<string, string> = {
  order_lookup: "bg-accent/10 text-accent border-accent/20",
  crm_search: "bg-purple/10 text-purple border-purple/20",
  email_draft: "bg-warning/10 text-warning border-warning/20",
  shipping_api: "bg-success/10 text-success border-success/20",
  classifier: "bg-danger/10 text-danger border-danger/20",
  kb_search: "bg-accent/10 text-accent border-accent/20",
  ticket_update: "bg-purple/10 text-purple border-purple/20",
  calculator: "bg-warning/10 text-warning border-warning/20",
};

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

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { agent, steps, loading } = useAgent(id!);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="text-center py-16 text-text-muted">Agent not found</div>
    );
  }

  const riskTimeline = generateRiskTimeline(agent.current_risk_score);

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate("/agents")}
          className="mt-1 p-2 rounded-lg border border-white/[0.06] text-text-muted hover:text-text-primary hover:bg-white/[0.04] transition-all duration-150"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-text-primary font-mono">{agent.name}</h1>
            <Badge variant={agent.status} />
          </div>
          <p className="text-sm text-text-muted mt-1">
            {agent.total_steps.toLocaleString()} steps | {agent.total_cost.toFixed(2).replace('.', ',')} € total cost | Last seen {formatRelativeTime(agent.last_seen_at)}
          </p>
        </div>
        <RiskGauge score={agent.current_risk_score} />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Cost", value: `${agent.total_cost.toFixed(2).replace('.', ',')} €`, icon: DollarSign, color: "text-success" },
          { label: "Total Tokens", value: agent.total_tokens.toLocaleString(), icon: Zap, color: "text-accent" },
          { label: "Total Steps", value: agent.total_steps.toLocaleString(), icon: Terminal, color: "text-purple" },
          { label: "CO2 Emitted", value: `${agent.total_co2_grams.toFixed(1)}g`, icon: Clock, color: "text-warning" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="p-4">
            <div className="flex items-center gap-3">
              <div className={cn("w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center", color)}>
                <Icon className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[11px] text-text-muted uppercase tracking-wider">{label}</p>
                <p className="text-lg font-semibold font-mono text-text-primary">{value}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Risk Over Time Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Risk Score Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={riskTimeline} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                {/* Safe zone */}
                <ReferenceArea y1={0} y2={49} fill="rgba(16,185,129,0.03)" />
                {/* Warning zone */}
                <ReferenceArea y1={50} y2={74} fill="rgba(245,158,11,0.03)" />
                {/* Danger zone */}
                <ReferenceArea y1={75} y2={100} fill="rgba(239,68,68,0.04)" />
                <XAxis
                  dataKey="time"
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
                  stroke="#00D4FF"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#00D4FF", stroke: "#0A0A0F", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Recent Steps */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Steps</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            {steps.map((step) => (
              <div
                key={step.step_number}
                className="flex items-start gap-4 p-3 rounded-lg hover:bg-white/[0.02] transition-colors duration-150 group"
              >
                {/* Step number */}
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white/[0.04] flex items-center justify-center">
                  <span className="text-xs font-mono text-text-muted">#{step.step_number}</span>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-1">
                  <p className="text-sm text-text-primary truncate">
                    <span className="text-text-muted">In: </span>
                    {step.input.length > 80 ? step.input.slice(0, 80) + "..." : step.input}
                  </p>
                  <p className="text-sm text-text-muted truncate">
                    <span className="text-text-muted/60">Out: </span>
                    {step.output.length > 100 ? step.output.slice(0, 100) + "..." : step.output}
                  </p>
                </div>

                {/* Tool badge */}
                {step.tool && (
                  <span className={cn(
                    "flex-shrink-0 text-[10px] font-mono px-2 py-1 rounded-md border",
                    toolColors[step.tool] || "bg-white/[0.04] text-text-muted border-white/[0.06]"
                  )}>
                    {step.tool}
                  </span>
                )}

                {/* Meta */}
                <div className="flex-shrink-0 text-right space-y-0.5">
                  <p className="text-xs font-mono text-text-muted">{step.cost.toFixed(3).replace('.', ',')} €</p>
                  <p className="text-[10px] text-text-muted/60">{formatRelativeTime(step.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
