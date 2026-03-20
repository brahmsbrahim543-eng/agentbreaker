import { NavLink } from "react-router-dom";
import {
  ShieldCheck,
  LayoutDashboard,
  Bot,
  AlertTriangle,
  BarChart3,
  Play,
  Settings2,
} from "lucide-react";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/playground", label: "Playground", icon: Play },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

export function Sidebar() {
  return (
    <aside className="w-60 h-screen bg-surface border-r border-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-border">
        <ShieldCheck className="w-6 h-6 text-accent shrink-0" />
        <span className="text-base font-bold text-accent tracking-tight">
          AgentBreaker
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-3 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-accent/10 text-accent border-l-2 border-accent pl-[10px]"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-hover border-l-2 border-transparent pl-[10px]"
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <p className="text-[11px] text-text-muted/60">
          AgentBreaker v1.0
        </p>
      </div>
    </aside>
  );
}
