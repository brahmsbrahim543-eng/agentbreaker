import { useState, useEffect } from "react";
import { ShieldCheck, Lock, Eye, EyeOff } from "lucide-react";

const SITE_PASSWORD = "1234@@aZEr";
const GATE_KEY = "ab_site_access";

export function useSiteAccess() {
  const [granted, setGranted] = useState(() => {
    try {
      return sessionStorage.getItem(GATE_KEY) === "granted";
    } catch {
      return false;
    }
  });

  const grant = () => {
    sessionStorage.setItem(GATE_KEY, "granted");
    setGranted(true);
  };

  return { granted, grant };
}

export function SiteGate({ children }: { children: React.ReactNode }) {
  const { granted, grant } = useSiteAccess();
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  if (granted) return <>{children}</>;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === SITE_PASSWORD) {
      grant();
    } else {
      setError(true);
      setTimeout(() => setError(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-4">
            <ShieldCheck className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">AgentBreaker</h1>
          <p className="mt-2 text-sm text-text-muted">Private access — authorized personnel only</p>
        </div>

        {/* Password form */}
        <form onSubmit={handleSubmit} className="rounded-2xl border border-border bg-surface/40 p-8">
          <div className="flex items-center gap-2 mb-6">
            <Lock className="w-4 h-4 text-text-muted" />
            <span className="text-sm font-medium text-text-primary">Enter access code</span>
          </div>

          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Access code"
              autoFocus
              className={`w-full px-4 py-3 rounded-lg border bg-background text-text-primary placeholder:text-text-muted/50 text-sm font-mono focus:outline-none focus:ring-2 transition-all ${
                error
                  ? "border-danger focus:ring-danger/30"
                  : "border-border focus:border-accent focus:ring-accent/20"
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          {error && (
            <p className="mt-2 text-xs text-danger">Invalid access code. Contact the administrator.</p>
          )}

          <button
            type="submit"
            className="mt-4 w-full px-4 py-3 bg-accent text-background font-semibold rounded-lg text-sm hover:brightness-110 transition-all"
          >
            Access Platform
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-text-muted">
          Confidential — Not for public distribution
        </p>
      </div>
    </div>
  );
}
