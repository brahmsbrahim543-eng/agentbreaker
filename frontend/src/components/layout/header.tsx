import { useLocation } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuth } from "../../contexts/auth-context";

const routeTitles: Record<string, string> = {
  "/overview": "Overview",
  "/agents": "Agents",
  "/incidents": "Incidents",
  "/analytics": "Analytics",
  "/playground": "Playground",
  "/settings": "Settings",
};

function getPageTitle(pathname: string): string {
  if (routeTitles[pathname]) return routeTitles[pathname];
  if (pathname.startsWith("/agents/")) return "Agent Details";
  if (pathname.startsWith("/incidents/")) return "Incident Details";
  return "Dashboard";
}

export function Header() {
  const { user, org, logout } = useAuth();
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  return (
    <header className="h-16 border-b border-border bg-background flex items-center justify-between px-6 shrink-0">
      <h1 className="text-lg font-semibold text-text-primary tracking-tight">
        {title}
      </h1>

      <div className="flex items-center gap-4">
        {org && (
          <span className="text-sm text-text-muted font-medium">
            {org.name}
          </span>
        )}

        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-full bg-accent/15 text-accent flex items-center justify-center text-xs font-bold select-none"
            title={user?.name}
          >
            {initials}
          </div>

          <button
            onClick={logout}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-200 cursor-pointer"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
