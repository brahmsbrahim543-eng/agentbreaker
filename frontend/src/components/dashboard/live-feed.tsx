import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────
type EventType = "agent_started" | "warning" | "killed";

interface FeedEvent {
  id: string;
  type: EventType;
  agent: string;
  description: string;
  timestamp: Date;
}

// ── Constants ──────────────────────────────────────────────────────
const AGENT_NAMES = [
  "gpt-4o-billing",
  "claude-research",
  "gemini-summarizer",
  "codex-deploy",
  "sonnet-scraper",
  "o1-analyst",
  "deepseek-miner",
  "llama-translator",
  "mistral-router",
  "phi-validator",
  "qwen-indexer",
  "command-r-ops",
];

const EVENT_TEMPLATES: Record<
  EventType,
  { descriptions: string[]; color: string; bgColor: string }
> = {
  agent_started: {
    descriptions: [
      "started monitoring",
      "entered active scan",
      "resumed execution",
      "initialized pipeline",
    ],
    color: "bg-accent",
    bgColor: "bg-accent/5",
  },
  warning: {
    descriptions: [
      "risk score 67 \u2014 similarity warning",
      "cost threshold 80% reached",
      "latency spike detected (3.2s)",
      "token budget 90% consumed",
      "anomalous output pattern",
      "risk score 54 \u2014 drift warning",
    ],
    color: "bg-warning",
    bgColor: "bg-warning/5",
  },
  killed: {
    descriptions: [
      "killed \u2014 semantic loop detected, 8,40 € saved",
      "killed \u2014 hallucination cascade, 12,30 € saved",
      "killed \u2014 infinite retry pattern, 5,70 € saved",
      "killed \u2014 cost runaway blocked, 23,10 € saved",
      "killed \u2014 output divergence, 6,80 € saved",
    ],
    color: "bg-danger",
    bgColor: "bg-danger/5",
  },
};

const MAX_EVENTS = 15;

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomType(): EventType {
  const r = Math.random();
  if (r < 0.4) return "agent_started";
  if (r < 0.7) return "warning";
  return "killed";
}

function formatAgo(d: Date): string {
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

// ── Component ──────────────────────────────────────────────────────
export function LiveFeed() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const counterRef = useRef(0);

  const addEvent = useCallback(() => {
    const type = randomType();
    const tpl = EVENT_TEMPLATES[type];

    const evt: FeedEvent = {
      id: `evt-${++counterRef.current}`,
      type,
      agent: pick(AGENT_NAMES),
      description: pick(tpl.descriptions),
      timestamp: new Date(),
    };

    setEvents((prev) => [evt, ...prev].slice(0, MAX_EVENTS));
  }, []);

  useEffect(() => {
    // Seed a few events immediately
    for (let i = 0; i < 5; i++) {
      setTimeout(() => addEvent(), i * 200);
    }

    const interval = setInterval(
      () => addEvent(),
      2000 + Math.random() * 1500
    );
    return () => clearInterval(interval);
  }, [addEvent]);

  // Update relative timestamps every 10s
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 10_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col h-full max-h-[380px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-60" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent" />
        </span>
        <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Live Feed
        </span>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1 -mr-1">
        <AnimatePresence initial={false}>
          {events.map((evt) => {
            const tpl = EVENT_TEMPLATES[evt.type];
            return (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, x: 24, height: 0 }}
                animate={{ opacity: 1, x: 0, height: "auto" }}
                exit={{ opacity: 0, x: -12, height: 0 }}
                transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={cn(
                  "flex items-start gap-3 px-3 py-2.5 rounded-lg",
                  "hover:bg-white/[0.03] transition-colors duration-150"
                )}
              >
                {/* Dot */}
                <div className="mt-1.5 flex-shrink-0">
                  <div className={cn("w-2 h-2 rounded-full", tpl.color)} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-medium text-text-primary truncate">
                      {evt.agent}
                    </span>
                    <span className="text-[10px] text-text-muted flex-shrink-0">
                      {formatAgo(evt.timestamp)}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed mt-0.5 truncate">
                    {evt.description}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
