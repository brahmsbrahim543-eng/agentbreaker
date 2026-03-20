import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import {
  SlidersHorizontal,
  DollarSign,
  Bell,
  Key,
  Copy,
  Check,
  Trash2,
  Plus,
  X,
} from "lucide-react";
import { cn } from "../lib/utils";

/* ─── Types ─── */

interface DetectionConfig {
  similarity: number;
  diminishingReturns: number;
  contextGrowth: number;
  errorCascade: number;
  costVelocity: number;
  killThreshold: number;
}

interface BudgetConfig {
  maxPerAgent: number;
  maxPerProjectMonth: number;
  maxStepsPerAgent: number;
}

interface NotificationChannel {
  enabled: boolean;
  value: string;
}

interface ApiKey {
  id: string;
  prefix: string;
  name: string;
  created: string;
  lastUsed: string;
}

/* ─── Slider Component ─── */

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  const display = format ? format(value) : value.toString();

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-text-muted">{label}</span>
        <span className="text-sm font-mono text-accent">{display}</span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full h-1.5 appearance-none cursor-pointer rounded-full bg-white/[0.06] outline-none
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent
            [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,212,255,0.4)] [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:relative [&::-webkit-slider-thumb]:z-10
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full
            [&::-moz-range-thumb]:bg-accent [&::-moz-range-thumb]:border-none [&::-moz-range-thumb]:cursor-pointer"
          style={{
            background: `linear-gradient(to right, #00D4FF ${pct}%, rgba(255,255,255,0.06) ${pct}%)`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-text-muted/50">
        <span>{format ? format(min) : min}</span>
        <span>{format ? format(max) : max}</span>
      </div>
    </div>
  );
}

/* ─── Tabs ─── */

const TABS = [
  { id: "detection", label: "Detection", icon: SlidersHorizontal },
  { id: "budget", label: "Budget", icon: DollarSign },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "apikeys", label: "API Keys", icon: Key },
] as const;

type TabId = (typeof TABS)[number]["id"];

/* ─── Defaults ─── */

const DEFAULT_DETECTION: DetectionConfig = {
  similarity: 0.85,
  diminishingReturns: 0.1,
  contextGrowth: 0.2,
  errorCascade: 3,
  costVelocity: 3.0,
  killThreshold: 75,
};

const DEFAULT_BUDGET: BudgetConfig = {
  maxPerAgent: 50,
  maxPerProjectMonth: 5000,
  maxStepsPerAgent: 100,
};

const INITIAL_KEYS: ApiKey[] = [
  {
    id: "1",
    prefix: "ab_live_...7f3a",
    name: "Production",
    created: "2025-12-01",
    lastUsed: "2026-03-17",
  },
  {
    id: "2",
    prefix: "ab_live_...c92e",
    name: "Staging",
    created: "2026-01-15",
    lastUsed: "2026-03-16",
  },
  {
    id: "3",
    prefix: "ab_test_...4d1b",
    name: "Development",
    created: "2026-02-20",
    lastUsed: "2026-03-10",
  },
];

/* ─── Page ─── */

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("detection");
  const [detection, setDetection] = useState<DetectionConfig>({ ...DEFAULT_DETECTION });
  const [budget, setBudget] = useState<BudgetConfig>({ ...DEFAULT_BUDGET });
  const [saved, setSaved] = useState(false);

  // Notifications
  const [email, setEmail] = useState<NotificationChannel>({
    enabled: true,
    value: "alerts@company.com",
  });
  const [slack, setSlack] = useState<NotificationChannel>({
    enabled: false,
    value: "",
  });
  const [pagerduty, setPagerduty] = useState<NotificationChannel>({
    enabled: false,
    value: "",
  });

  // API Keys
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(INITIAL_KEYS);
  const [showNewKey, setShowNewKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  const handleSave = useCallback(() => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, []);

  const handleCreateKey = useCallback(() => {
    const hex = Array.from({ length: 32 }, () =>
      Math.floor(Math.random() * 16).toString(16)
    ).join("");
    const fullKey = `ab_live_${hex}`;
    const newKey: ApiKey = {
      id: Date.now().toString(),
      prefix: `ab_live_...${hex.slice(-4)}`,
      name: newKeyName || "Unnamed Key",
      created: new Date().toISOString().split("T")[0],
      lastUsed: "Never",
    };
    setApiKeys((prev) => [...prev, newKey]);
    setGeneratedKey(fullKey);
    setNewKeyName("");
  }, [newKeyName]);

  const handleCopyKey = useCallback(() => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  }, [generatedKey]);

  const handleRevokeKey = useCallback((id: string) => {
    setApiKeys((prev) => prev.filter((k) => k.id !== id));
    setConfirmRevoke(null);
  }, []);

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-semibold text-text-primary">Settings</h1>
        <p className="text-text-muted text-sm mt-1">
          Configure detection thresholds, budgets, and integrations
        </p>
      </motion.div>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 bg-white/[0.02] rounded-xl border border-border w-fit">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer",
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-muted hover:text-text-primary hover:bg-white/[0.04]"
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {/* ─── Detection Tab ─── */}
          {activeTab === "detection" && (
            <Card className="p-6">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-6">
                Detection Thresholds
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
                <Slider
                  label="Similarity Threshold"
                  value={detection.similarity}
                  min={0.5}
                  max={1.0}
                  step={0.01}
                  onChange={(v) => setDetection((p) => ({ ...p, similarity: v }))}
                  format={(v) => v.toFixed(2)}
                />
                <Slider
                  label="Diminishing Returns"
                  value={detection.diminishingReturns}
                  min={0.01}
                  max={0.3}
                  step={0.01}
                  onChange={(v) => setDetection((p) => ({ ...p, diminishingReturns: v }))}
                  format={(v) => v.toFixed(2)}
                />
                <Slider
                  label="Context Growth"
                  value={detection.contextGrowth}
                  min={0.05}
                  max={0.5}
                  step={0.01}
                  onChange={(v) => setDetection((p) => ({ ...p, contextGrowth: v }))}
                  format={(v) => v.toFixed(2)}
                />
                <Slider
                  label="Error Cascade"
                  value={detection.errorCascade}
                  min={1}
                  max={10}
                  step={1}
                  onChange={(v) => setDetection((p) => ({ ...p, errorCascade: v }))}
                />
                <Slider
                  label="Cost Velocity"
                  value={detection.costVelocity}
                  min={1.5}
                  max={10.0}
                  step={0.1}
                  onChange={(v) => setDetection((p) => ({ ...p, costVelocity: v }))}
                  format={(v) => v.toFixed(1) + "x"}
                />
                <Slider
                  label="Kill Threshold"
                  value={detection.killThreshold}
                  min={50}
                  max={100}
                  step={1}
                  onChange={(v) => setDetection((p) => ({ ...p, killThreshold: v }))}
                />
              </div>
              <div className="flex items-center gap-3 mt-8 pt-6 border-t border-border">
                <Button
                  variant="ghost"
                  onClick={() => setDetection({ ...DEFAULT_DETECTION })}
                >
                  Reset to Defaults
                </Button>
                <Button onClick={handleSave}>
                  {saved ? (
                    <>
                      <Check className="w-4 h-4" /> Saved
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </div>
            </Card>
          )}

          {/* ─── Budget Tab ─── */}
          {activeTab === "budget" && (
            <Card className="p-6">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-6">
                Budget Limits
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="space-y-2">
                  <label className="text-sm text-text-muted">Max € per Agent</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">
                      €
                    </span>
                    <input
                      type="number"
                      value={budget.maxPerAgent}
                      onChange={(e) =>
                        setBudget((p) => ({
                          ...p,
                          maxPerAgent: parseInt(e.target.value) || 0,
                        }))
                      }
                      className="w-full bg-white/[0.03] border border-border rounded-lg px-3 pl-7 py-2.5 text-sm text-text-primary
                        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-text-muted">
                    Max € per Project / Month
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">
                      €
                    </span>
                    <input
                      type="number"
                      value={budget.maxPerProjectMonth}
                      onChange={(e) =>
                        setBudget((p) => ({
                          ...p,
                          maxPerProjectMonth: parseInt(e.target.value) || 0,
                        }))
                      }
                      className="w-full bg-white/[0.03] border border-border rounded-lg px-3 pl-7 py-2.5 text-sm text-text-primary
                        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-text-muted">Max Steps per Agent</label>
                  <input
                    type="number"
                    value={budget.maxStepsPerAgent}
                    onChange={(e) =>
                      setBudget((p) => ({
                        ...p,
                        maxStepsPerAgent: parseInt(e.target.value) || 0,
                      }))
                    }
                    className="w-full bg-white/[0.03] border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary
                      focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all"
                  />
                </div>
              </div>
              <div className="flex items-center gap-3 mt-8 pt-6 border-t border-border">
                <Button onClick={handleSave}>
                  {saved ? (
                    <>
                      <Check className="w-4 h-4" /> Saved
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </div>
            </Card>
          )}

          {/* ─── Notifications Tab ─── */}
          {activeTab === "notifications" && (
            <Card className="p-6">
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-6">
                Notification Channels
              </h2>
              <div className="space-y-6">
                {/* Email */}
                <div className="flex items-center gap-4">
                  <div className="flex-1 space-y-2">
                    <label className="text-sm text-text-muted">Email</label>
                    <input
                      type="email"
                      value={email.value}
                      onChange={(e) =>
                        setEmail((p) => ({ ...p, value: e.target.value }))
                      }
                      placeholder="alerts@company.com"
                      className="w-full bg-white/[0.03] border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary
                        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all
                        placeholder:text-text-muted/40"
                    />
                  </div>
                  <Toggle
                    enabled={email.enabled}
                    onChange={(v) => setEmail((p) => ({ ...p, enabled: v }))}
                  />
                </div>

                {/* Slack */}
                <div className="flex items-center gap-4">
                  <div className="flex-1 space-y-2">
                    <label className="text-sm text-text-muted">Slack Webhook URL</label>
                    <input
                      type="url"
                      value={slack.value}
                      onChange={(e) =>
                        setSlack((p) => ({ ...p, value: e.target.value }))
                      }
                      placeholder="https://hooks.slack.com/services/..."
                      className="w-full bg-white/[0.03] border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary
                        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all
                        placeholder:text-text-muted/40"
                    />
                  </div>
                  <Toggle
                    enabled={slack.enabled}
                    onChange={(v) => setSlack((p) => ({ ...p, enabled: v }))}
                  />
                </div>

                {/* PagerDuty */}
                <div className="flex items-center gap-4">
                  <div className="flex-1 space-y-2">
                    <label className="text-sm text-text-muted">
                      PagerDuty Integration Key
                    </label>
                    <input
                      type="text"
                      value={pagerduty.value}
                      onChange={(e) =>
                        setPagerduty((p) => ({ ...p, value: e.target.value }))
                      }
                      placeholder="e93facc04764012345abcdef..."
                      className="w-full bg-white/[0.03] border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary
                        focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-all
                        placeholder:text-text-muted/40"
                    />
                  </div>
                  <Toggle
                    enabled={pagerduty.enabled}
                    onChange={(v) => setPagerduty((p) => ({ ...p, enabled: v }))}
                  />
                </div>
              </div>

              <p className="text-xs text-text-muted/60 mt-6 italic">
                Configure notification endpoints in your environment settings
              </p>

              <div className="flex items-center gap-3 mt-6 pt-6 border-t border-border">
                <Button onClick={handleSave}>
                  {saved ? (
                    <>
                      <Check className="w-4 h-4" /> Saved
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </div>
            </Card>
          )}

          {/* ─── API Keys Tab ─── */}
          {activeTab === "apikeys" && (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-medium text-text-muted uppercase tracking-wide">
                  API Keys
                </h2>
                <Button
                  size="sm"
                  onClick={() => {
                    setShowNewKey(true);
                    setGeneratedKey(null);
                  }}
                >
                  <Plus className="w-3.5 h-3.5" /> Create New Key
                </Button>
              </div>

              {/* Generated key banner */}
              <AnimatePresence>
                {generatedKey && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-6"
                  >
                    <div className="bg-accent-dim border border-accent/20 rounded-xl p-4">
                      <p className="text-xs text-accent mb-2 font-medium">
                        Copy your API key now. It will not be shown again.
                      </p>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 bg-black/30 rounded-lg px-3 py-2 text-xs font-mono text-text-primary break-all">
                          {generatedKey}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleCopyKey}
                        >
                          {copiedKey ? (
                            <Check className="w-3.5 h-3.5" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </Button>
                      </div>
                      <button
                        onClick={() => setGeneratedKey(null)}
                        className="text-xs text-text-muted hover:text-text-primary mt-2 cursor-pointer"
                      >
                        Dismiss
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* New key form */}
              <AnimatePresence>
                {showNewKey && !generatedKey && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-6"
                  >
                    <div className="bg-white/[0.02] border border-border rounded-xl p-4">
                      <div className="flex items-end gap-3">
                        <div className="flex-1 space-y-2">
                          <label className="text-xs text-text-muted">Key Name</label>
                          <input
                            type="text"
                            value={newKeyName}
                            onChange={(e) => setNewKeyName(e.target.value)}
                            placeholder="e.g. Production, CI/CD"
                            className="w-full bg-white/[0.03] border border-border rounded-lg px-3 py-2 text-sm text-text-primary
                              focus:outline-none focus:border-accent/50 transition-all placeholder:text-text-muted/40"
                            onKeyDown={(e) => e.key === "Enter" && handleCreateKey()}
                          />
                        </div>
                        <Button size="sm" onClick={handleCreateKey}>
                          Generate
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setShowNewKey(false);
                            setNewKeyName("");
                          }}
                        >
                          <X className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Keys table */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left text-xs text-text-muted font-medium py-3 pr-4">
                        Key
                      </th>
                      <th className="text-left text-xs text-text-muted font-medium py-3 pr-4">
                        Name
                      </th>
                      <th className="text-left text-xs text-text-muted font-medium py-3 pr-4">
                        Created
                      </th>
                      <th className="text-left text-xs text-text-muted font-medium py-3 pr-4">
                        Last Used
                      </th>
                      <th className="text-right text-xs text-text-muted font-medium py-3">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiKeys.map((key) => (
                      <tr
                        key={key.id}
                        className="border-b border-border/50 hover:bg-white/[0.01] transition-colors"
                      >
                        <td className="py-3 pr-4">
                          <code className="text-xs font-mono text-text-primary bg-white/[0.04] px-2 py-1 rounded">
                            {key.prefix}
                          </code>
                        </td>
                        <td className="py-3 pr-4 text-sm text-text-primary">
                          {key.name}
                        </td>
                        <td className="py-3 pr-4 text-sm text-text-muted">
                          {key.created}
                        </td>
                        <td className="py-3 pr-4 text-sm text-text-muted">
                          {key.lastUsed}
                        </td>
                        <td className="py-3 text-right">
                          {confirmRevoke === key.id ? (
                            <div className="flex items-center justify-end gap-2">
                              <span className="text-xs text-danger">Confirm?</span>
                              <Button
                                size="sm"
                                variant="danger"
                                onClick={() => handleRevokeKey(key.id)}
                              >
                                Revoke
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setConfirmRevoke(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setConfirmRevoke(key.id)}
                            >
                              <Trash2 className="w-3.5 h-3.5 text-danger/70" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/* ─── Toggle Component ─── */

function Toggle({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={() => onChange(!enabled)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200",
        enabled ? "bg-accent" : "bg-white/[0.1]"
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform duration-200",
          enabled ? "translate-x-5" : "translate-x-0"
        )}
      />
    </button>
  );
}
