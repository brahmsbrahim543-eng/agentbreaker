import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/auth-context";
import { SiteGate } from "./components/site-gate";
import { Layout } from "./components/layout/layout";
import LoginPage from "./pages/login";
import LandingPage from "./pages/landing";
import OverviewPage from "./pages/overview";
import AgentsPage from "./pages/agents";
import AgentDetailPage from "./pages/agent-detail";
import IncidentsPage from "./pages/incidents";
import IncidentDetailPage from "./pages/incident-detail";
import AnalyticsPage from "./pages/analytics";
import PlaygroundPage from "./pages/playground";
import SettingsPage from "./pages/settings";
import ROICalculator from "./pages/roi-calculator";
import DocsPage from "./pages/docs";
import InvestorsPage from "./pages/investors";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen bg-background flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <SiteGate>
      <AuthProvider>
        <Routes>
          <Route path="/landing" element={<LandingPage />} />
          <Route path="/roi" element={<ROICalculator />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/investors" element={<InvestorsPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/agents/:id" element={<AgentDetailPage />} />
            <Route path="/incidents" element={<IncidentsPage />} />
            <Route path="/incidents/:id" element={<IncidentDetailPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/playground" element={<PlaygroundPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </AuthProvider>
    </SiteGate>
  );
}
