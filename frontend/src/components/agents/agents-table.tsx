import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useAgents, type Agent } from "../../hooks/use-agents";
import { Badge } from "../ui/badge";
import { RiskBar } from "./risk-bar";
import { cn, formatRelativeTime } from "../../lib/utils";

const PER_PAGE = 10;

export function AgentsTable() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { agents, total, loading } = useAgents({
    status: statusFilter || undefined,
    page,
    per_page: PER_PAGE,
    search,
  });

  const totalPages = Math.ceil(total / PER_PAGE);
  const startItem = (page - 1) * PER_PAGE + 1;
  const endItem = Math.min(page * PER_PAGE, total);

  function handleRowClick(agent: Agent) {
    navigate(`/agents/${agent.id}`);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all duration-200"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent/40 transition-all duration-200 cursor-pointer appearance-none"
        >
          <option value="" className="bg-surface">All Statuses</option>
          <option value="running" className="bg-surface">Running</option>
          <option value="warning" className="bg-surface">Warning</option>
          <option value="killed" className="bg-surface">Killed</option>
          <option value="idle" className="bg-surface">Idle</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="text-left text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3">Name</th>
              <th className="text-left text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3">Status</th>
              <th className="text-left text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3 min-w-[160px]">Risk Score</th>
              <th className="text-right text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3">Total Cost</th>
              <th className="text-right text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3">Steps</th>
              <th className="text-right text-[11px] font-medium text-text-muted uppercase tracking-wider px-4 py-3">Last Active</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-white/[0.03]">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-2.5">
                      <div className="h-4 bg-white/[0.04] rounded animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : agents.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-12 text-text-muted text-sm">
                  No agents found
                </td>
              </tr>
            ) : (
              agents.map((agent) => (
                <tr
                  key={agent.id}
                  onClick={() => handleRowClick(agent)}
                  className={cn(
                    "border-b border-white/[0.03] cursor-pointer transition-colors duration-150",
                    "hover:bg-white/[0.03]",
                    "active:bg-white/[0.05]"
                  )}
                >
                  <td className="px-4 py-2.5 max-w-[180px]">
                    <span className="text-sm font-medium text-text-primary font-mono truncate block">
                      {agent.name}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={agent.status} size="sm" />
                  </td>
                  <td className="px-4 py-2.5">
                    <RiskBar score={agent.current_risk_score} />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="text-sm font-mono text-text-primary">
                      {agent.total_cost.toFixed(2).replace('.', ',')} €
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="text-sm font-mono text-text-muted">
                      {agent.total_steps.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="text-xs text-text-muted">
                      {formatRelativeTime(agent.last_seen_at)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-text-muted">
            Showing {startItem}-{endItem} of {total}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-md border border-white/[0.06] text-text-muted hover:text-text-primary hover:bg-white/[0.04] disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (page <= 3) {
                pageNum = i + 1;
              } else if (page >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = page - 2 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={cn(
                    "w-8 h-8 rounded-md text-xs font-medium transition-all duration-150",
                    pageNum === page
                      ? "bg-accent/10 text-accent border border-accent/20"
                      : "text-text-muted hover:text-text-primary hover:bg-white/[0.04]"
                  )}
                >
                  {pageNum}
                </button>
              );
            })}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-md border border-white/[0.06] text-text-muted hover:text-text-primary hover:bg-white/[0.04] disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
