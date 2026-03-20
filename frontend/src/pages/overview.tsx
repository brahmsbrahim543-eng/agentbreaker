import { DollarSign, Bot, AlertTriangle, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { useAnalytics } from "@/hooks/use-analytics";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { SavingsChart } from "@/components/dashboard/savings-chart";
import { LiveFeed } from "@/components/dashboard/live-feed";
import { ActivityHeatmap } from "@/components/dashboard/activity-heatmap";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { formatCurrency, formatNumber } from "@/lib/utils";

function getRiskColor(score: number): "success" | "warning" | "danger" {
  if (score < 30) return "success";
  if (score <= 60) return "warning";
  return "danger";
}

export default function OverviewPage() {
  const { overview, timeline, heatmap, loading } = useAnalytics();

  if (loading || !overview) {
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
    <div className="space-y-6">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">
          Overview
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Real-time agent monitoring and cost analytics
        </p>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Money Saved"
          value={formatCurrency(overview.total_savings)}
          icon={DollarSign}
          color="success"
          trend="+12.4%"
        />
        <KpiCard
          title="Active Agents"
          value={formatNumber(overview.active_agents)}
          icon={Bot}
          color="accent"
          trend="+84"
        />
        <KpiCard
          title="Incidents Today"
          value={formatNumber(overview.incidents_today)}
          icon={AlertTriangle}
          color="warning"
          trend="-3"
        />
        <KpiCard
          title="Avg Risk Score"
          value={overview.avg_risk_score.toFixed(1)}
          icon={Activity}
          color={getRiskColor(overview.avg_risk_score)}
          trend={overview.avg_risk_score < 40 ? "Low" : overview.avg_risk_score < 65 ? "Medium" : "High"}
          trendColor={getRiskColor(overview.avg_risk_score)}
        />
      </div>

      {/* Middle row: Chart + Live Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Savings chart */}
        <motion.div
          className="lg:col-span-8"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Cost Savings (30 Days)</CardTitle>
            </CardHeader>
            <CardContent>
              <SavingsChart data={timeline} />
            </CardContent>
          </Card>
        </motion.div>

        {/* Live feed */}
        <motion.div
          className="lg:col-span-4"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
        >
          <Card className="h-full">
            <CardContent className="p-5 h-full">
              <LiveFeed />
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Activity heatmap */}
      {heatmap && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Agent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <ActivityHeatmap data={heatmap} />
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
