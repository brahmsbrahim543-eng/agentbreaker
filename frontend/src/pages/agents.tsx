import { Bot } from "lucide-react";
import { Card } from "../components/ui/card";
import { AgentsTable } from "../components/agents/agents-table";

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Bot className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Agents</h1>
          <p className="text-sm text-text-muted">Monitor and manage all AI agents in your organization</p>
        </div>
      </div>

      {/* Table Card */}
      <Card className="p-5">
        <AgentsTable />
      </Card>
    </div>
  );
}
