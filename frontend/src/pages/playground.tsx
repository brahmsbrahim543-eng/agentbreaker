import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import {
  RefreshCw,
  TrendingUp,
  AlertOctagon,
  Play,
  RotateCcw,
  ArrowLeft,
  Search,
  DollarSign,
  XCircle,
  Clock,
  Layers,
} from "lucide-react";
import { cn } from "../lib/utils";

/* ═══════════════════════════════════════════
   SIMULATION DATA
   ═══════════════════════════════════════════ */

interface SimStep {
  output: string;
  risk: number;
  similarity?: number;
  cost?: number;
  error?: string;
  tool: string;
  warning?: string;
  kill?: boolean;
}

interface Scenario {
  id: string;
  title: string;
  description: string;
  duration: string;
  icon: typeof RefreshCw;
  killReason: string;
  costAvoided: string;
  detectors: {
    similarity: number;
    costVelocity: number;
    errorRate: number;
    contextGrowth: number;
    diminishing: number;
  };
  steps: SimStep[];
}

const SCENARIOS: Scenario[] = [
  {
    id: "semantic_loop",
    title: "Semantic Loop",
    description:
      "An agent searches for information and keeps reformulating the same query",
    duration: "~15 seconds",
    icon: RefreshCw,
    killReason: "Semantic Loop Detected",
    costAvoided: "12,40 €",
    detectors: {
      similarity: 93,
      costVelocity: 22,
      errorRate: 0,
      contextGrowth: 35,
      diminishing: 48,
    },
    steps: [
      {
        output:
          "Scientists estimate roughly 200 billion trillion stars in the observable universe.",
        risk: 12,
        similarity: 0,
        tool: "search",
      },
      {
        output:
          "Astronomers believe approximately 200 sextillion stars exist in the known universe.",
        risk: 34,
        similarity: 66,
        tool: "search",
      },
      {
        output:
          "Current research suggests around two hundred billion trillion stars in the universe.",
        risk: 56,
        similarity: 78,
        tool: "search",
      },
      {
        output:
          "The latest data indicates there are roughly 200 billion trillion stars.",
        risk: 72,
        similarity: 85,
        tool: "search",
        warning: "Similarity threshold exceeded: 85%",
      },
      {
        output:
          "Based on observations, the estimated star count is approximately 200 sextillion.",
        risk: 88,
        similarity: 93,
        tool: "search",
        kill: true,
      },
    ],
  },
  {
    id: "cost_explosion",
    title: "Cost Explosion",
    description:
      "Cost per step doubles each time as the agent scales up operations",
    duration: "~12 seconds",
    icon: TrendingUp,
    killReason: "Cost Velocity Exceeded",
    costAvoided: "847,20 €",
    detectors: {
      similarity: 12,
      costVelocity: 96,
      errorRate: 0,
      contextGrowth: 55,
      diminishing: 30,
    },
    steps: [
      {
        output: "Processing batch 1: 100 records analyzed successfully.",
        risk: 8,
        cost: 0.12,
        tool: "compute",
      },
      {
        output: "Scaling up. Processing batch 2: 1,000 records with GPU acceleration.",
        risk: 25,
        cost: 1.44,
        tool: "compute",
      },
      {
        output:
          "Auto-scaling triggered. Batch 3: 10,000 records across 8 instances.",
        risk: 52,
        cost: 17.28,
        tool: "compute",
        warning: "Cost velocity: 12x per step",
      },
      {
        output:
          "Maximum parallelism. Batch 4: 100,000 records on 64 GPU instances.",
        risk: 78,
        cost: 207.36,
        tool: "compute",
        warning: "Cost velocity: 12x per step - CRITICAL",
      },
      {
        output: "Requesting 512 GPU instances for batch 5: 1M records.",
        risk: 95,
        cost: 2488.32,
        tool: "compute",
        kill: true,
      },
    ],
  },
  {
    id: "error_cascade",
    title: "Error Cascade",
    description: "Same tool fails repeatedly and the agent keeps retrying",
    duration: "~10 seconds",
    icon: AlertOctagon,
    killReason: "Error Cascade Detected",
    costAvoided: "3,80 €",
    detectors: {
      similarity: 45,
      costVelocity: 15,
      errorRate: 100,
      contextGrowth: 42,
      diminishing: 60,
    },
    steps: [
      {
        output: "Attempting to connect to database at db.internal:5432...",
        risk: 10,
        error: "ECONNREFUSED",
        tool: "db_query",
      },
      {
        output: "Retrying with exponential backoff (2s). Connecting to db.internal:5432...",
        risk: 30,
        error: "ECONNREFUSED",
        tool: "db_query",
      },
      {
        output: "Retry 3/10. Attempting alternate host db-replica.internal:5432...",
        risk: 55,
        error: "ECONNREFUSED",
        tool: "db_query",
        warning: "3 consecutive failures on db_query",
      },
      {
        output: "Retry 4/10. Trying with increased timeout (30s)...",
        risk: 75,
        error: "ETIMEDOUT after 30000ms",
        tool: "db_query",
        warning: "Error cascade threshold reached",
      },
      {
        output: "Retry 5/10. Attempting connection with fallback credentials...",
        risk: 92,
        error: "ECONNREFUSED",
        tool: "db_query",
        kill: true,
      },
    ],
  },
];

/* ═══════════════════════════════════════════
   RISK GAUGE SVG
   ═══════════════════════════════════════════ */

function RiskGauge({
  value,
  isKilled,
}: {
  value: number;
  isKilled: boolean;
}) {
  const size = 200;
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const startAngle = 135;
  const totalAngle = 270;
  const progress = Math.min(value / 100, 1);
  const dashOffset = circumference * (1 - (progress * totalAngle) / 360);

  const getColor = (v: number) => {
    if (v < 50) return "#10B981";
    if (v < 75) return "#F59E0B";
    return "#EF4444";
  };

  const color = getColor(value);

  return (
    <motion.div
      className="relative"
      animate={
        isKilled
          ? {
              scale: [1, 1.05, 1],
              filter: [
                "drop-shadow(0 0 0px transparent)",
                "drop-shadow(0 0 30px rgba(239,68,68,0.6))",
                "drop-shadow(0 0 15px rgba(239,68,68,0.3))",
              ],
            }
          : {}
      }
      transition={
        isKilled ? { duration: 0.6, repeat: 2, repeatType: "reverse" } : {}
      }
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${(circumference * totalAngle) / 360} ${circumference}`}
          transform={`rotate(${startAngle} ${size / 2} ${size / 2})`}
        />
        {/* Progress arc */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${(circumference * totalAngle) / 360} ${circumference}`}
          strokeDashoffset={dashOffset}
          transform={`rotate(${startAngle} ${size / 2} ${size / 2})`}
          style={{
            filter: `drop-shadow(0 0 8px ${color}80)`,
            transition: "stroke-dashoffset 0.5s ease, stroke 0.3s ease",
          }}
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          key={value}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-4xl font-mono font-bold"
          style={{ color }}
        >
          {value}
        </motion.span>
        <span className="text-xs text-text-muted mt-1">RISK SCORE</span>
      </div>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════
   DETECTOR BARS
   ═══════════════════════════════════════════ */

function DetectorBars({
  detectors,
  progress,
}: {
  detectors: Scenario["detectors"];
  progress: number;
}) {
  const bars = [
    { label: "Similarity", value: detectors.similarity, color: "#A855F7" },
    { label: "Cost Velocity", value: detectors.costVelocity, color: "#F59E0B" },
    { label: "Error Rate", value: detectors.errorRate, color: "#EF4444" },
    { label: "Context Growth", value: detectors.contextGrowth, color: "#00D4FF" },
    { label: "Diminishing", value: detectors.diminishing, color: "#EAB308" },
  ];

  return (
    <div className="space-y-2 mt-4">
      {bars.map((bar) => {
        const currentVal = Math.round(bar.value * progress);
        return (
          <div key={bar.label} className="flex items-center gap-3">
            <span className="text-[10px] text-text-muted w-20 text-right shrink-0">
              {bar.label}
            </span>
            <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: bar.color }}
                initial={{ width: 0 }}
                animate={{ width: `${currentVal}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
            <span
              className="text-[10px] font-mono w-8 text-right"
              style={{ color: bar.color }}
            >
              {currentVal}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════
   STEP LOG ENTRY
   ═══════════════════════════════════════════ */

function StepEntry({
  step,
  index,
  startTime,
}: {
  step: SimStep;
  index: number;
  startTime: Date;
}) {
  const time = new Date(startTime.getTime() + index * 3000);
  const timeStr = time.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const toolIcons: Record<string, typeof Search> = {
    search: Search,
    compute: DollarSign,
    db_query: Layers,
  };
  const ToolIcon = toolIcons[step.tool] || Search;

  const riskBlocks = Math.round(step.risk / 10);
  const riskBar =
    "\u2588".repeat(riskBlocks) + "\u2591".repeat(10 - riskBlocks);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "border-l-2 pl-4 py-3",
        step.kill
          ? "border-danger"
          : step.warning
          ? "border-warning"
          : "border-white/10"
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-text-muted text-xs font-mono">[{timeStr}]</span>
        <span
          className={cn(
            "text-xs font-medium",
            step.kill ? "text-danger" : "text-text-primary"
          )}
        >
          Step {index + 1}
        </span>
      </div>
      <div className="flex items-center gap-1.5 mb-1">
        <ToolIcon className="w-3 h-3 text-accent" />
        <span className="text-xs text-accent font-mono">
          {step.tool}(
          {step.tool === "search"
            ? '"number of stars universe"'
            : step.tool === "compute"
            ? '"process_batch"'
            : '"SELECT * FROM users"'}
          )
        </span>
      </div>
      <p
        className={cn(
          "text-xs ml-4 mb-1",
          step.error ? "text-danger/80" : "text-text-muted"
        )}
      >
        {step.error ? (
          <>
            <XCircle className="w-3 h-3 inline mr-1 text-danger" />
            Error: {step.error}
          </>
        ) : (
          <>
            <span className="text-text-muted/60">{"\u2192"} </span>
            &quot;{step.output}&quot;
          </>
        )}
      </p>
      {step.cost !== undefined && (
        <p className="text-xs ml-4 mb-1 text-warning">
          <DollarSign className="w-3 h-3 inline mr-0.5" />
          Step cost: {step.cost.toFixed(2).replace('.', ',')} €
        </p>
      )}
      <div className="flex items-center gap-2 ml-4">
        <span className="text-xs text-text-muted">Risk:</span>
        <span
          className={cn(
            "text-xs font-mono",
            step.risk >= 75
              ? "text-danger"
              : step.risk >= 50
              ? "text-warning"
              : "text-success"
          )}
        >
          {step.risk}{" "}
        </span>
        <span
          className={cn(
            "text-xs font-mono tracking-tighter",
            step.risk >= 75
              ? "text-danger/60"
              : step.risk >= 50
              ? "text-warning/60"
              : "text-success/60"
          )}
        >
          {riskBar}
        </span>
      </div>
      {step.warning && (
        <p className="text-xs ml-4 mt-1 text-warning font-medium">
          {"\u26A0"} {step.warning}
        </p>
      )}
      {step.kill && (
        <motion.p
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-xs ml-4 mt-2 text-danger font-bold"
        >
          {"\u{1F534}"} KILLED
        </motion.p>
      )}
    </motion.div>
  );
}

/* ═══════════════════════════════════════════
   MAIN PLAYGROUND PAGE
   ═══════════════════════════════════════════ */

export default function PlaygroundPage() {
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentStepIdx, setCurrentStepIdx] = useState(-1);
  const [isKilled, setIsKilled] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef(new Date());

  const cleanup = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentStepIdx]);

  const runSimulation = useCallback(
    (scenario: Scenario) => {
      cleanup();
      setActiveScenario(scenario);
      setIsRunning(true);
      setCurrentStepIdx(-1);
      setIsKilled(false);
      setShowResult(false);
      startTimeRef.current = new Date();

      let idx = -1;
      intervalRef.current = setInterval(() => {
        idx++;
        if (idx >= scenario.steps.length) {
          cleanup();
          setIsRunning(false);
          setIsKilled(true);
          setTimeout(() => setShowResult(true), 800);
          return;
        }
        setCurrentStepIdx(idx);
        if (scenario.steps[idx].kill) {
          cleanup();
          setIsRunning(false);
          setIsKilled(true);
          setTimeout(() => setShowResult(true), 800);
        }
      }, 1500);
    },
    [cleanup]
  );

  const resetAll = useCallback(() => {
    cleanup();
    setActiveScenario(null);
    setIsRunning(false);
    setCurrentStepIdx(-1);
    setIsKilled(false);
    setShowResult(false);
  }, [cleanup]);

  const currentRisk =
    currentStepIdx >= 0 && activeScenario
      ? activeScenario.steps[currentStepIdx].risk
      : 0;

  const detectorProgress =
    activeScenario && activeScenario.steps.length > 0
      ? Math.min((currentStepIdx + 1) / activeScenario.steps.length, 1)
      : 0;

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-semibold text-text-primary">Playground</h1>
        <p className="text-text-muted text-sm mt-1">
          Watch AgentBreaker detect and kill runaway agents in real time
        </p>
      </motion.div>

      <AnimatePresence mode="wait">
        {!activeScenario ? (
          /* ─── Scenario Cards ─── */
          <motion.div
            key="cards"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -16 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            {SCENARIOS.map((scenario, i) => {
              const Icon = scenario.icon;
              return (
                <motion.div
                  key={scenario.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1, duration: 0.4 }}
                >
                  <Card className="p-6 group hover:border-accent/30 transition-all duration-300 cursor-pointer h-full flex flex-col">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-lg bg-accent-dim flex items-center justify-center">
                        <Icon className="w-5 h-5 text-accent" />
                      </div>
                      <h3 className="text-base font-semibold text-text-primary">
                        {scenario.title}
                      </h3>
                    </div>
                    <p className="text-sm text-text-muted mb-4 flex-1">
                      {scenario.description}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-xs text-text-muted">
                        <Clock className="w-3.5 h-3.5" />
                        {scenario.duration}
                      </div>
                      <Button
                        size="sm"
                        onClick={() => runSimulation(scenario)}
                        className="group-hover:shadow-[0_0_24px_-4px_rgba(0,212,255,0.5)]"
                      >
                        <Play className="w-3.5 h-3.5" />
                        Run Scenario
                      </Button>
                    </div>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>
        ) : (
          /* ─── Simulation View ─── */
          <motion.div
            key="simulation"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="space-y-6"
          >
            {/* Header */}
            <div className="flex items-center gap-3">
              <button
                onClick={resetAll}
                className="text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-2">
                {(() => {
                  const Icon = activeScenario.icon;
                  return <Icon className="w-5 h-5 text-accent" />;
                })()}
                <h2 className="text-lg font-semibold text-text-primary">
                  {activeScenario.title}
                </h2>
              </div>
              {isRunning && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 ml-auto"
                >
                  <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  <span className="text-xs text-accent font-medium">
                    Monitoring...
                  </span>
                </motion.div>
              )}
            </div>

            {/* Two columns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* LEFT: Risk Gauge */}
              <Card className="p-6 flex flex-col items-center">
                <RiskGauge value={currentRisk} isKilled={isKilled} />
                <DetectorBars
                  detectors={activeScenario.detectors}
                  progress={detectorProgress}
                />
              </Card>

              {/* RIGHT: Step Log */}
              <div className="bg-[#0D1117] rounded-xl border border-white/[0.06] p-4 overflow-y-auto max-h-[500px] min-h-[400px]">
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-white/[0.06]">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
                    <div className="w-3 h-3 rounded-full bg-[#FEBC2E]" />
                    <div className="w-3 h-3 rounded-full bg-[#28C840]" />
                  </div>
                  <span className="text-xs text-text-muted font-mono ml-2">
                    agent-monitor
                  </span>
                </div>

                {currentStepIdx < 0 && isRunning && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center gap-2 text-xs text-text-muted"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                    Initializing agent monitor...
                  </motion.div>
                )}

                <AnimatePresence>
                  {activeScenario.steps
                    .slice(0, currentStepIdx + 1)
                    .map((step, i) => (
                      <StepEntry
                        key={i}
                        step={step}
                        index={i}
                        startTime={startTimeRef.current}
                      />
                    ))}
                </AnimatePresence>
                <div ref={logEndRef} />
              </div>
            </div>

            {/* Result Banner */}
            <AnimatePresence>
              {showResult && (
                <motion.div
                  initial={{ opacity: 0, y: 20, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ type: "spring", damping: 20, stiffness: 300 }}
                >
                  <Card className="p-6 border-danger/30 bg-danger/[0.03]">
                    <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-3 h-3 rounded-full bg-danger animate-pulse" />
                          <h3 className="text-lg font-bold text-danger">
                            AGENT KILLED
                          </h3>
                        </div>
                        <p className="text-sm text-text-muted">
                          {activeScenario.killReason}
                        </p>
                      </div>
                      <div className="flex gap-8">
                        <div className="text-center">
                          <p className="text-xl font-bold font-mono text-success">
                            {activeScenario.costAvoided}
                          </p>
                          <p className="text-xs text-text-muted">cost avoided</p>
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold font-mono text-text-primary">
                            {activeScenario.steps.length}
                          </p>
                          <p className="text-xs text-text-muted">steps</p>
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold font-mono text-text-primary">
                            {activeScenario.steps.length * 3}s
                          </p>
                          <p className="text-xs text-text-muted">duration</p>
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <Button
                          variant="outline"
                          onClick={() => runSimulation(activeScenario)}
                        >
                          <RotateCcw className="w-4 h-4" />
                          Run Again
                        </Button>
                        <Button onClick={resetAll}>
                          <ArrowLeft className="w-4 h-4" />
                          Try Another
                        </Button>
                      </div>
                    </div>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
