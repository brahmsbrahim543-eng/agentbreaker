import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Zap, Leaf, Smartphone } from "lucide-react";
import { api } from "../lib/api";

// ── Types for API responses ──────────────────────────────────────
interface TopAgent {
  agent_name: string;
  total_cost: number;
}

interface IncidentDistItem {
  type: string;
  count: number;
  percentage: number;
}

interface CarbonReport {
  total_kwh_saved: number;
  total_co2_saved_kg: number;
  equivalences: Record<string, number>;
  monthly_trend: { month: string; co2_saved_kg: number }[];
}

// ── Fallback mock data ───────────────────────────────────────────
const MOCK_TOP_AGENTS: TopAgent[] = [
  { agent_name: "data-pipeline-v3", total_cost: 14800 },
  { agent_name: "research-assistant", total_cost: 12300 },
  { agent_name: "code-reviewer-pro", total_cost: 9700 },
  { agent_name: "customer-support-ai", total_cost: 8200 },
  { agent_name: "content-generator", total_cost: 7100 },
];

const TYPE_COLOR_MAP: Record<string, string> = {
  semantic_loop: "#A855F7",
  error_cascade: "#EF4444",
  cost_spike: "#F59E0B",
  diminishing_returns: "#EAB308",
  context_bloat: "#00D4FF",
};

const TYPE_LABEL_MAP: Record<string, string> = {
  semantic_loop: "Semantic Loop",
  error_cascade: "Error Cascade",
  cost_spike: "Cost Spike",
  diminishing_returns: "Diminishing Returns",
  context_bloat: "Context Bloat",
};

function DarkTooltip({ active, payload, label, suffix = "" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#16161E] border border-white/10 rounded-lg px-3 py-2 shadow-xl text-xs">
      <p className="text-text-muted mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-text-primary font-medium">
          {typeof entry.value === "number"
            ? entry.value.toLocaleString("fr-FR")
            : entry.value}
          {suffix}
        </p>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const [topAgents, setTopAgents] = useState<{ name: string; cost: number }[]>([]);
  const [incidentDist, setIncidentDist] = useState<{ name: string; value: number; color: string }[]>([]);
  const [carbon, setCarbon] = useState<CarbonReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      setLoading(true);

      const [agents, dist, carbonData] = await Promise.all([
        api.get<TopAgent[]>("/api/v1/analytics/top-agents").catch(() => null),
        api.get<IncidentDistItem[]>("/api/v1/analytics/incident-distribution").catch(() => null),
        api.get<CarbonReport>("/api/v1/analytics/carbon-report").catch(() => null),
      ]);

      if (cancelled) return;

      // Map top agents: API returns {agent_name, total_cost}
      const mappedAgents = (agents ?? MOCK_TOP_AGENTS).map((a) => ({
        name: a.agent_name,
        cost: a.total_cost,
      }));
      // Reverse so highest cost is at top of horizontal bar chart
      setTopAgents([...mappedAgents].reverse());

      // Map incident distribution: API returns {type, count, percentage}
      if (dist && dist.length > 0) {
        setIncidentDist(
          dist.map((d) => ({
            name: TYPE_LABEL_MAP[d.type] ?? d.type,
            value: d.percentage,
            color: TYPE_COLOR_MAP[d.type] ?? "#8B8B9E",
          }))
        );
      } else {
        setIncidentDist([
          { name: "Semantic Loop", value: 45, color: "#A855F7" },
          { name: "Error Cascade", value: 25, color: "#EF4444" },
          { name: "Cost Spike", value: 15, color: "#F59E0B" },
          { name: "Diminishing Returns", value: 10, color: "#EAB308" },
          { name: "Context Bloat", value: 5, color: "#00D4FF" },
        ]);
      }

      setCarbon(carbonData);
      setLoading(false);
    }

    fetchAll();
    return () => { cancelled = true; };
  }, []);

  // Prepare CO2 monthly trend for chart
  const co2Monthly = carbon?.monthly_trend?.map((m) => ({
    month: m.month,
    saved: m.co2_saved_kg,
  })) ?? [
    { month: "Oct", saved: 180 },
    { month: "Nov", saved: 260 },
    { month: "Dec", saved: 340 },
    { month: "Jan", saved: 420 },
    { month: "Feb", saved: 510 },
    { month: "Mar", saved: 620 },
  ];

  // Format large numbers
  const kwhSaved = carbon ? carbon.total_kwh_saved.toLocaleString() : "7,300";
  const co2Saved = carbon ? Math.round(carbon.total_co2_saved_kg).toLocaleString() : "2,847";
  const phoneCharges = carbon?.equivalences?.phone_charges
    ? Math.round(carbon.equivalences.phone_charges).toLocaleString()
    : "346";

  // Cost trend from savings timeline (reuse the 30-day savings data)
  const [costTrend, setCostTrend] = useState<{ date: string; cost: number }[]>([]);

  useEffect(() => {
    api
      .get<{ date: string; cost_saved: number }[]>("/api/v1/analytics/savings-timeline?days=90")
      .then((data) => {
        setCostTrend(
          data.map((d) => ({
            date: new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            cost: d.cost_saved,
          }))
        );
      })
      .catch(() => {
        // Generate fallback
        const fallback = [];
        let cost = 4200;
        const now = new Date();
        for (let i = 89; i >= 0; i--) {
          const date = new Date(now);
          date.setDate(date.getDate() - i);
          cost += (Math.random() - 0.55) * 300;
          cost = Math.max(800, cost);
          fallback.push({
            date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            cost: Math.round(cost),
          });
        }
        setCostTrend(fallback);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <p className="text-sm text-text-muted">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-semibold text-text-primary">Analytics</h1>
        <p className="text-text-muted text-sm mt-1">
          Cost intelligence and incident trends across your fleet
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.5 }}
        >
          <Card className="p-6 h-full">
            <CardHeader className="p-0 pb-6">
              <CardTitle>Top 10 Costliest Agents</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ResponsiveContainer width="100%" height={380}>
                <BarChart
                  data={topAgents}
                  layout="vertical"
                  margin={{ left: 8, right: 24, top: 0, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#8B8B9E", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) =>
                      v >= 1000 ? `${(v / 1000).toFixed(0)}K €` : `${v.toLocaleString("fr-FR")} €`
                    }
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    tick={{ fill: "#8B8B9E", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={130}
                  />
                  <Tooltip
                    content={<DarkTooltip suffix=" €" />}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  />
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#00D4FF" />
                      <stop offset="100%" stopColor="#EF4444" />
                    </linearGradient>
                  </defs>
                  <Bar
                    dataKey="cost"
                    fill="url(#barGradient)"
                    radius={[0, 4, 4, 0]}
                    barSize={20}
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <Card className="p-6 h-full">
            <CardHeader className="p-0 pb-6">
              <CardTitle>Incident Type Distribution</CardTitle>
            </CardHeader>
            <CardContent className="p-0 flex flex-col items-center">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={incidentDist}
                    cx="50%"
                    cy="50%"
                    innerRadius={70}
                    outerRadius={110}
                    dataKey="value"
                    stroke="none"
                    paddingAngle={2}
                  >
                    {incidentDist.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }: any) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-[#16161E] border border-white/10 rounded-lg px-3 py-2 shadow-xl text-xs">
                          <p className="text-text-primary font-medium">
                            {d.name}: {d.value.toFixed(1)}%
                          </p>
                        </div>
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap justify-center gap-x-5 gap-y-2 mt-2">
                {incidentDist.map((item) => (
                  <div key={item.name} className="flex items-center gap-2 text-xs">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-text-muted">
                      {item.name}{" "}
                      <span className="text-text-primary font-medium">
                        {item.value.toFixed(1)}%
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {costTrend.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
        >
          <Card className="p-6">
            <CardHeader className="p-0 pb-6">
              <CardTitle>Cost Savings Trend</CardTitle>
              <p className="text-xs text-text-muted mt-1">
                Daily cost savings since deploying AgentBreaker
              </p>
            </CardHeader>
            <CardContent className="p-0">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart
                  data={costTrend}
                  margin={{ left: 8, right: 24, top: 8, bottom: 0 }}
                >
                  <CartesianGrid
                    stroke="rgba(255,255,255,0.03)"
                    strokeDasharray="4 4"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#8B8B9E", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    interval={14}
                  />
                  <YAxis
                    tick={{ fill: "#8B8B9E", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) =>
                      v >= 1000 ? `${(v / 1000).toFixed(1)}K €` : `${v.toLocaleString("fr-FR")} €`
                    }
                  />
                  <Tooltip content={<DarkTooltip suffix=" €" />} />
                  <Line
                    type="monotone"
                    dataKey="cost"
                    stroke="#00D4FF"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{
                      r: 4,
                      fill: "#00D4FF",
                      stroke: "#0A0A0F",
                      strokeWidth: 2,
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
      >
        <Card className="p-6">
          <CardHeader className="p-0 pb-6">
            <CardTitle>Environmental Impact</CardTitle>
            <p className="text-xs text-text-muted mt-1">
              Estimated resource savings from prevented runaway agents
            </p>
          </CardHeader>
          <CardContent className="p-0">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-accent-dim flex items-center justify-center shrink-0">
                  <Zap className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <p className="text-xl font-semibold text-text-primary font-mono">{kwhSaved}</p>
                  <p className="text-xs text-text-muted">kWh saved</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-success-dim flex items-center justify-center shrink-0">
                  <Leaf className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="text-xl font-semibold text-text-primary font-mono">{co2Saved}</p>
                  <p className="text-xs text-text-muted">kg CO2 avoided</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-purple-dim flex items-center justify-center shrink-0">
                  <Smartphone className="w-5 h-5 text-purple" />
                </div>
                <div>
                  <p className="text-xl font-semibold text-text-primary font-mono">{phoneCharges}</p>
                  <p className="text-xs text-text-muted">phone charges equiv.</p>
                </div>
              </div>
              <div>
                <p className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
                  Monthly CO2 Trend
                </p>
                <ResponsiveContainer width="100%" height={80}>
                  <LineChart data={co2Monthly}>
                    <Line
                      type="monotone"
                      dataKey="saved"
                      stroke="#10B981"
                      strokeWidth={2}
                      dot={{ r: 2, fill: "#10B981", stroke: "none" }}
                    />
                    <Tooltip
                      content={({ active, payload, label }: any) => {
                        if (!active || !payload?.length) return null;
                        return (
                          <div className="bg-[#16161E] border border-white/10 rounded-lg px-2 py-1 shadow-xl text-[10px]">
                            <span className="text-text-muted">{label}: </span>
                            <span className="text-success font-medium">
                              {payload[0].value} kg
                            </span>
                          </div>
                        );
                      }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
