import { useState, useEffect } from "react";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────
export interface OverviewData {
  total_savings: number;
  active_agents: number;
  incidents_today: number;
  avg_risk_score: number;
}

export interface TimelinePoint {
  date: string;
  cost_saved: number;
}

export interface HeatmapData {
  data: number[][];
  labels_x: string[];
  labels_y: string[];
}

interface AnalyticsState {
  overview: OverviewData | null;
  timeline: TimelinePoint[];
  heatmap: HeatmapData | null;
  loading: boolean;
  error: string | null;
}

// ── Mock data ──────────────────────────────────────────────────────
const MOCK_OVERVIEW: OverviewData = {
  total_savings: 847293,
  active_agents: 2847,
  incidents_today: 23,
  avg_risk_score: 34.2,
};

const MOCK_TIMELINE: TimelinePoint[] = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 86400000)
    .toISOString()
    .split("T")[0],
  cost_saved: 15000 + Math.random() * 20000 + i * 500,
}));

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const WEEKS = Array.from({ length: 12 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (11 - i) * 7);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
});

const MOCK_HEATMAP: HeatmapData = {
  data: Array.from({ length: 7 }, () =>
    Array.from({ length: 12 }, () => Math.floor(Math.random() * 100))
  ),
  labels_x: WEEKS,
  labels_y: DAYS,
};

// ── Hook ───────────────────────────────────────────────────────────
export function useAnalytics(): AnalyticsState {
  const [state, setState] = useState<AnalyticsState>({
    overview: null,
    timeline: [],
    heatmap: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      setState((s) => ({ ...s, loading: true, error: null }));

      // Fetch all three endpoints in parallel; fall back to mocks on failure
      const [overview, timeline, heatmap] = await Promise.all([
        api
          .get<OverviewData>("/api/v1/analytics/overview")
          .catch(() => null),
        api
          .get<TimelinePoint[]>("/api/v1/analytics/savings-timeline?days=30")
          .catch(() => null),
        api
          .get<HeatmapData>("/api/v1/analytics/heatmap")
          .catch(() => null),
      ]);

      if (cancelled) return;

      // Normalize: API returns avg_risk_score as 0–1, frontend expects 0–100
      const normalizedOverview = overview
        ? {
            ...overview,
            avg_risk_score:
              overview.avg_risk_score <= 1
                ? overview.avg_risk_score * 100
                : overview.avg_risk_score,
          }
        : MOCK_OVERVIEW;

      setState({
        overview: normalizedOverview,
        timeline: timeline?.length ? timeline : MOCK_TIMELINE,
        heatmap: heatmap ?? MOCK_HEATMAP,
        loading: false,
        error: null,
      });
    }

    fetchAll();

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
