import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Loader2 } from "lucide-react";
import { useAuth } from "../contexts/auth-context";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@agentbreaker.com");
  const [password, setPassword] = useState("AB2026secure!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/overview", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      navigate("/overview", { replace: true });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Invalid credentials"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      {/* Subtle radial glow behind card */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[600px] h-[600px] rounded-full bg-accent/[0.03] blur-[120px]" />
      </div>

      <Card variant="glow" className="w-full max-w-sm p-8 relative z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <ShieldCheck className="w-8 h-8 text-accent" />
          <span className="text-xl font-bold text-accent tracking-tight">
            AgentBreaker
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-danger/10 border border-danger/20 text-danger text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 text-sm text-text-primary placeholder:text-text-muted/50 outline-none transition-all duration-200 focus:border-accent/40 focus:ring-1 focus:ring-accent/20"
              placeholder="you@company.com"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 text-sm text-text-primary placeholder:text-text-muted/50 outline-none transition-all duration-200 focus:border-accent/40 focus:ring-1 focus:ring-accent/20"
              placeholder="Enter password"
              required
            />
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full mt-2"
            size="md"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              "Sign In"
            )}
          </Button>
        </form>

        <p className="text-center text-[11px] text-text-muted/60 mt-6">
          AgentBreaker v1.0 — Authorized access only
        </p>
      </Card>
    </div>
  );
}
