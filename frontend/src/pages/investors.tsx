import { useEffect, useRef, useState, FormEvent } from "react";
import { motion, useInView } from "framer-motion";
import {
  Shield,
  Zap,
  TrendingUp,
  AlertTriangle,
  Brain,
  Cpu,
  Globe,
  DollarSign,
  Users,
  Target,
  ChevronRight,
  Check,
  X,
  Minus,
  Mail,
  Send,
  Activity,
  Lock,
  BarChart3,
  ArrowRight,
  Clock,
  Layers,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ACCENT = "#00D4FF";
const PURPLE = "#A855F7";
const SUCCESS = "#10B981";
const DANGER = "#EF4444";
const WARNING = "#F59E0B";
const SURFACE = "#111118";
const BG = "#0A0A0F";

/* ------------------------------------------------------------------ */
/*  Animated counter                                                    */
/* ------------------------------------------------------------------ */

function useCountUp(end: number, duration = 2000) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * end));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView, end, duration]);

  return { value, ref };
}

/* ------------------------------------------------------------------ */
/*  Fade-in wrapper                                                     */
/* ------------------------------------------------------------------ */

const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: { opacity: 1, y: 0 },
};

function FadeIn({
  children,
  className = "",
  delay = 0,
  id,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  id?: string;
  style?: React.CSSProperties;
}) {
  return (
    <motion.div
      id={id}
      style={style}
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.25, 0.1, 0.25, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                     */
/* ------------------------------------------------------------------ */

function Section({
  children,
  className = "",
  id,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  id?: string;
  style?: React.CSSProperties;
}) {
  return (
    <section id={id} style={style} className={`py-24 px-6 md:px-12 lg:px-24 ${className}`}>
      <div className="max-w-6xl mx-auto">{children}</div>
    </section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-block text-xs font-semibold tracking-[0.2em] uppercase mb-4"
      style={{ color: ACCENT }}
    >
      {children}
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-3xl md:text-4xl font-bold mb-6" style={{ color: "#F5F5F7" }}>
      {children}
    </h2>
  );
}

/* ------------------------------------------------------------------ */
/*  TAM Chart Data                                                      */
/* ------------------------------------------------------------------ */

const tamData = [
  { year: "2024", tam: 2.1, sam: 0.4 },
  { year: "2025", tam: 2.8, sam: 0.7 },
  { year: "2026", tam: 3.6, sam: 1.2 },
  { year: "2027", tam: 4.7, sam: 1.9 },
  { year: "2028", tam: 5.9, sam: 2.8 },
  { year: "2029", tam: 7.4, sam: 3.9 },
  { year: "2030", tam: 8.9, sam: 5.2 },
  { year: "2031", tam: 9.6, sam: 6.1 },
  { year: "2032", tam: 10.1, sam: 7.0 },
  { year: "2033", tam: 10.7, sam: 7.8 },
];

/* ------------------------------------------------------------------ */
/*  Competitive data                                                    */
/* ------------------------------------------------------------------ */

type FeatureVal = "yes" | "partial" | "no";

interface Competitor {
  name: string;
  realTimeKill: FeatureVal;
  semanticDetection: FeatureVal;
  dimensions: string;
  costTracking: FeatureVal;
  selfHosted: FeatureVal;
  pricing: string;
}

const competitors: Competitor[] = [
  {
    name: "AgentBreaker",
    realTimeKill: "yes",
    semanticDetection: "yes",
    dimensions: "8",
    costTracking: "yes",
    selfHosted: "yes",
    pricing: "From \u20AC199/mo",
  },
  {
    name: "Portkey",
    realTimeKill: "no",
    semanticDetection: "no",
    dimensions: "2",
    costTracking: "yes",
    selfHosted: "no",
    pricing: "Usage-based",
  },
  {
    name: "LangSmith",
    realTimeKill: "no",
    semanticDetection: "partial",
    dimensions: "3",
    costTracking: "partial",
    selfHosted: "no",
    pricing: "From $39/mo",
  },
  {
    name: "Arize",
    realTimeKill: "no",
    semanticDetection: "partial",
    dimensions: "3",
    costTracking: "yes",
    selfHosted: "no",
    pricing: "Enterprise",
  },
  {
    name: "Galileo",
    realTimeKill: "no",
    semanticDetection: "yes",
    dimensions: "2",
    costTracking: "no",
    selfHosted: "no",
    pricing: "Enterprise",
  },
];

function FeatureIcon({ val }: { val: FeatureVal }) {
  if (val === "yes")
    return <Check className="w-5 h-5 mx-auto" style={{ color: SUCCESS }} />;
  if (val === "partial")
    return <Minus className="w-5 h-5 mx-auto" style={{ color: WARNING }} />;
  return <X className="w-5 h-5 mx-auto" style={{ color: DANGER }} />;
}

/* ------------------------------------------------------------------ */
/*  Detection engine cards                                              */
/* ------------------------------------------------------------------ */

const detectors = [
  {
    icon: Brain,
    name: "Semantic Similarity",
    desc: "Embedding-based loop detection via cosine similarity across agent outputs.",
  },
  {
    icon: Activity,
    name: "Reasoning Loop",
    desc: "Tarjan\u2019s SCC algorithm detects circular reasoning patterns in real-time.",
  },
  {
    icon: Target,
    name: "Goal Drift",
    desc: "Measures deviation between declared objectives and actual agent behavior.",
  },
  {
    icon: AlertTriangle,
    name: "Error Cascade",
    desc: "Tracks error propagation velocity across chained agent interactions.",
  },
  {
    icon: DollarSign,
    name: "Cost Velocity",
    desc: "Monitors spend rate per agent with adaptive threshold learning.",
  },
  {
    icon: BarChart3,
    name: "Token Entropy",
    desc: "Shannon entropy analysis to detect degrading output quality.",
  },
  {
    icon: Layers,
    name: "Context Inflation",
    desc: "Detects context window bloat from recursive self-referencing.",
  },
  {
    icon: TrendingUp,
    name: "Diminishing Returns",
    desc: "Identifies when agent iterations yield decreasing marginal value.",
  },
];

/* ------------------------------------------------------------------ */
/*  Architecture flow                                                   */
/* ------------------------------------------------------------------ */

function ArchitectureDiagram() {
  const steps = [
    { label: "AI Agent", sub: "Any LLM provider", icon: Cpu },
    { label: "SDK", sub: "Python / TS / REST", icon: Lock },
    { label: "Ingest API", sub: "< 5ms latency", icon: Zap },
    { label: "Detection Engine", sub: "8 detectors in parallel", icon: Shield },
    { label: "Kill Decision", sub: "Confidence scoring", icon: AlertTriangle },
    { label: "WebSocket", sub: "Real-time push", icon: Globe },
    { label: "Dashboard", sub: "Live monitoring", icon: Activity },
  ];

  return (
    <div className="relative overflow-x-auto pb-4">
      <div className="flex items-center gap-0 min-w-[900px]">
        {steps.map((step, i) => {
          const Icon = step.icon;
          const isEngine = step.label === "Detection Engine";
          return (
            <div key={step.label} className="flex items-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.4 }}
                className="flex flex-col items-center"
              >
                <div
                  className="w-24 h-24 rounded-xl flex flex-col items-center justify-center border"
                  style={{
                    background: isEngine
                      ? `linear-gradient(135deg, ${ACCENT}15, ${PURPLE}15)`
                      : `${SURFACE}`,
                    borderColor: isEngine ? ACCENT : "#1E1E2E",
                    boxShadow: isEngine ? `0 0 24px ${ACCENT}20` : "none",
                  }}
                >
                  <Icon
                    className="w-7 h-7 mb-1"
                    style={{ color: isEngine ? ACCENT : "#8B8B9E" }}
                  />
                  <span
                    className="text-[10px] font-semibold text-center leading-tight px-1"
                    style={{ color: "#F5F5F7" }}
                  >
                    {step.label}
                  </span>
                </div>
                <span
                  className="text-[9px] mt-2 text-center"
                  style={{ color: "#8B8B9E" }}
                >
                  {step.sub}
                </span>
              </motion.div>
              {i < steps.length - 1 && (
                <div className="flex items-center mx-1">
                  <div className="w-6 h-px" style={{ background: "#1E1E2E" }} />
                  <ChevronRight
                    className="w-4 h-4 -mx-1"
                    style={{ color: ACCENT }}
                  />
                  <div className="w-6 h-px" style={{ background: "#1E1E2E" }} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Pricing card                                                        */
/* ------------------------------------------------------------------ */

function PricingCard({
  tier,
  price,
  agents,
  features,
  highlighted,
}: {
  tier: string;
  price: string;
  agents: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="relative rounded-2xl p-8 border flex flex-col"
      style={{
        background: highlighted
          ? `linear-gradient(180deg, ${ACCENT}08, ${SURFACE})`
          : SURFACE,
        borderColor: highlighted ? ACCENT : "#1E1E2E",
        boxShadow: highlighted ? `0 0 40px ${ACCENT}15` : "none",
      }}
    >
      {highlighted && (
        <span
          className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-bold tracking-widest uppercase px-4 py-1 rounded-full"
          style={{ background: ACCENT, color: BG }}
        >
          Most Popular
        </span>
      )}
      <h3 className="text-xl font-bold mb-1" style={{ color: "#F5F5F7" }}>
        {tier}
      </h3>
      <p className="text-sm mb-6" style={{ color: "#8B8B9E" }}>
        {agents}
      </p>
      <div className="mb-6">
        <span className="text-4xl font-bold" style={{ color: "#F5F5F7" }}>
          {price}
        </span>
        <span className="text-sm" style={{ color: "#8B8B9E" }}>
          /mo
        </span>
      </div>
      <ul className="space-y-3 flex-1">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm" style={{ color: "#8B8B9E" }}>
            <Check className="w-4 h-4 mt-0.5 shrink-0" style={{ color: SUCCESS }} />
            {f}
          </li>
        ))}
      </ul>
      <button
        className="mt-8 w-full py-3 rounded-lg font-semibold text-sm transition-all duration-200"
        style={{
          background: highlighted ? ACCENT : "transparent",
          color: highlighted ? BG : ACCENT,
          border: `1px solid ${highlighted ? ACCENT : ACCENT}40`,
        }}
        onMouseEnter={(e) => {
          if (!highlighted) {
            e.currentTarget.style.background = `${ACCENT}15`;
          }
        }}
        onMouseLeave={(e) => {
          if (!highlighted) {
            e.currentTarget.style.background = "transparent";
          }
        }}
      >
        Get Started
      </button>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chart Tooltip                                                       */
/* ------------------------------------------------------------------ */

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}) {
  if (!active || !payload) return null;
  return (
    <div
      className="rounded-lg px-4 py-3 border text-sm"
      style={{ background: SURFACE, borderColor: "#1E1E2E" }}
    >
      <p className="font-semibold mb-1" style={{ color: "#F5F5F7" }}>
        {label}
      </p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.dataKey === "tam" ? ACCENT : PURPLE }}>
          {p.dataKey === "tam" ? "TAM" : "SAM"}: ${p.value}B
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function InvestorsPage() {
  const agentsProtected = useCountUp(1247);
  const organizations = useCountUp(89);
  const savedMillions = useCountUp(24, 2500);
  const uptime = useCountUp(9997, 2500);

  const [formData, setFormData] = useState({ name: "", email: "", message: "" });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen" style={{ background: BG, color: "#F5F5F7" }}>
      {/* ============================================================ */}
      {/*  HERO                                                         */}
      {/* ============================================================ */}
      <section className="relative min-h-screen flex items-center justify-center px-6 overflow-hidden">
        {/* Background gradient orbs */}
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-20 blur-[120px] -top-48 -left-48"
          style={{ background: ACCENT }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-15 blur-[100px] -bottom-32 -right-32"
          style={{ background: PURPLE }}
        />

        <div className="relative text-center max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div
              className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8 border"
              style={{
                background: `${ACCENT}10`,
                borderColor: `${ACCENT}30`,
                color: ACCENT,
              }}
            >
              <Lock className="w-3 h-3" />
              Confidential — Investor Access Only
            </div>

            <h1
              className="text-5xl md:text-7xl font-bold tracking-tight mb-6"
              style={{
                background: `linear-gradient(135deg, #F5F5F7 0%, ${ACCENT} 50%, ${PURPLE} 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              AgentBreaker
            </h1>
            <p
              className="text-xl md:text-2xl font-light mb-4"
              style={{ color: "#F5F5F7" }}
            >
              The Circuit Breaker for AI Agents
            </p>
            <p
              className="text-base md:text-lg max-w-2xl mx-auto mb-10 leading-relaxed"
              style={{ color: "#8B8B9E" }}
            >
              Real-time detection and automated kill-switch for runaway AI agents.
              8-dimensional analysis engine that prevents catastrophic cost overruns
              before they happen.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="#solution"
                className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg font-semibold text-sm transition-all duration-200"
                style={{ background: ACCENT, color: BG }}
              >
                View the Technology
                <ArrowRight className="w-4 h-4" />
              </a>
              <a
                href="#ask"
                className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg font-semibold text-sm border transition-all duration-200"
                style={{ borderColor: `${ACCENT}40`, color: ACCENT }}
              >
                The Ask
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  THE PROBLEM                                                   */}
      {/* ============================================================ */}
      <Section id="problem">
        <FadeIn>
          <SectionLabel>The Problem</SectionLabel>
          <SectionTitle>
            AI Agents Are Burning Money — And Nobody&rsquo;s Watching
          </SectionTitle>
        </FadeIn>

        <div className="grid md:grid-cols-3 gap-6 mt-12">
          {[
            {
              stat: "$8K\u2013$23K",
              unit: "/month",
              label: "Average undetected agent overspend per enterprise deployment",
              icon: DollarSign,
              color: DANGER,
            },
            {
              stat: "73%",
              unit: "",
              label: "Of enterprise AI deployments exceed their compute budget within 90 days",
              icon: TrendingUp,
              color: WARNING,
            },
            {
              stat: "0",
              unit: " tools",
              label: "Native circuit breakers exist for autonomous AI agents today",
              icon: Shield,
              color: ACCENT,
            },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <FadeIn key={item.label} delay={i * 0.1}>
                <div
                  className="rounded-2xl p-8 border h-full"
                  style={{ background: SURFACE, borderColor: "#1E1E2E" }}
                >
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                    style={{ background: `${item.color}15` }}
                  >
                    <Icon className="w-6 h-6" style={{ color: item.color }} />
                  </div>
                  <div className="mb-3">
                    <span className="text-4xl font-bold" style={{ color: item.color }}>
                      {item.stat}
                    </span>
                    <span className="text-lg" style={{ color: "#8B8B9E" }}>
                      {item.unit}
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: "#8B8B9E" }}>
                    {item.label}
                  </p>
                </div>
              </FadeIn>
            );
          })}
        </div>

        <FadeIn delay={0.3}>
          <div
            className="mt-8 rounded-xl p-6 border-l-4 text-sm leading-relaxed"
            style={{
              background: `${DANGER}08`,
              borderColor: DANGER,
              color: "#8B8B9E",
            }}
          >
            <strong style={{ color: "#F5F5F7" }}>Real-world scenario:</strong>{" "}
            A single runaway ReAct agent loop can exhaust a $50K monthly budget in
            under 4 hours. Multi-agent orchestration systems compound the risk
            exponentially — each agent can spawn sub-agents, creating cascading cost
            explosions with no built-in safeguard.
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  MARKET OPPORTUNITY                                            */}
      {/* ============================================================ */}
      <Section id="market" className="border-t" style={{ borderColor: "#1E1E2E" } as React.CSSProperties}>
        <FadeIn>
          <SectionLabel>Market Opportunity</SectionLabel>
          <SectionTitle>A $10.7B Market with No Incumbent</SectionTitle>
          <p className="text-base leading-relaxed max-w-3xl" style={{ color: "#8B8B9E" }}>
            AI in Observability is projected to reach $10.7B by 2033 at 22.5% CAGR.
            The agentic AI market itself is forecast at $52.62B by 2030. AI agent
            monitoring is becoming non-negotiable infrastructure for any enterprise
            deploying autonomous systems.
          </p>
        </FadeIn>

        <FadeIn delay={0.2}>
          <div
            className="mt-12 rounded-2xl p-8 border"
            style={{ background: SURFACE, borderColor: "#1E1E2E" }}
          >
            <h3 className="text-sm font-semibold mb-6" style={{ color: "#8B8B9E" }}>
              AI Observability Market Growth (TAM vs SAM, $B)
            </h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tamData}>
                  <defs>
                    <linearGradient id="gradTam" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={ACCENT} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={ACCENT} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradSam" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={PURPLE} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={PURPLE} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" />
                  <XAxis
                    dataKey="year"
                    tick={{ fill: "#8B8B9E", fontSize: 12 }}
                    axisLine={{ stroke: "#1E1E2E" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#8B8B9E", fontSize: 12 }}
                    axisLine={{ stroke: "#1E1E2E" }}
                    tickLine={false}
                    tickFormatter={(v) => `$${v}B`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="tam"
                    stroke={ACCENT}
                    strokeWidth={2}
                    fill="url(#gradTam)"
                  />
                  <Area
                    type="monotone"
                    dataKey="sam"
                    stroke={PURPLE}
                    strokeWidth={2}
                    fill="url(#gradSam)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex gap-6 mt-4">
              <div className="flex items-center gap-2 text-xs" style={{ color: "#8B8B9E" }}>
                <div className="w-3 h-1 rounded" style={{ background: ACCENT }} />
                TAM — AI Observability
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: "#8B8B9E" }}>
                <div className="w-3 h-1 rounded" style={{ background: PURPLE }} />
                SAM — Agent-specific Monitoring
              </div>
            </div>
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  WHY NOW                                                       */}
      {/* ============================================================ */}
      <Section id="why-now">
        <FadeIn>
          <SectionLabel>Why Now</SectionLabel>
          <SectionTitle>The Window Is Open</SectionTitle>
        </FadeIn>

        <div className="grid md:grid-cols-2 gap-6 mt-12">
          {[
            {
              icon: AlertTriangle,
              title: "Gartner 2026 Warning",
              body: "Gartner explicitly warns about multiagent system risk in their 2026 strategic technology trends. AI agent governance is now a board-level concern.",
            },
            {
              icon: Shield,
              title: "NIST AI Risk Framework Updated",
              body: "NIST updated the AI Risk Management Framework to address autonomous agent behavior, creating regulatory tailwind for monitoring solutions.",
            },
            {
              icon: DollarSign,
              title: "73% Budget Overruns",
              body: "Enterprise AI deployments consistently exceed compute budgets. CFOs are demanding cost controls before greenlighting further agent adoption.",
            },
            {
              icon: TrendingUp,
              title: "JetStream Security: $34M Seed",
              body: "JetStream Security raised $34M seed for AI governance — validating the market and setting the valuation floor for the category.",
            },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <FadeIn key={item.title} delay={i * 0.1}>
                <div
                  className="rounded-2xl p-8 border h-full"
                  style={{ background: SURFACE, borderColor: "#1E1E2E" }}
                >
                  <Icon className="w-6 h-6 mb-4" style={{ color: ACCENT }} />
                  <h3
                    className="text-lg font-semibold mb-3"
                    style={{ color: "#F5F5F7" }}
                  >
                    {item.title}
                  </h3>
                  <p className="text-sm leading-relaxed" style={{ color: "#8B8B9E" }}>
                    {item.body}
                  </p>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </Section>

      {/* ============================================================ */}
      {/*  THE SOLUTION                                                  */}
      {/* ============================================================ */}
      <Section id="solution" className="border-t" style={{ borderColor: "#1E1E2E" } as React.CSSProperties}>
        <FadeIn>
          <SectionLabel>The Solution</SectionLabel>
          <SectionTitle>8-Dimensional Detection Engine</SectionTitle>
          <p className="text-base leading-relaxed max-w-3xl mb-4" style={{ color: "#8B8B9E" }}>
            AgentBreaker analyzes agent behavior across 8 orthogonal dimensions
            simultaneously. When anomalies compound, the system triggers an
            automated kill-switch via WebSocket — not an alert, not a notification,
            a hard stop.
          </p>
        </FadeIn>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-12">
          {detectors.map((d, i) => {
            const Icon = d.icon;
            return (
              <FadeIn key={d.name} delay={i * 0.05}>
                <div
                  className="group rounded-xl p-6 border transition-all duration-300 h-full"
                  style={{ background: SURFACE, borderColor: "#1E1E2E" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = `${ACCENT}60`;
                    e.currentTarget.style.boxShadow = `0 0 24px ${ACCENT}10`;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "#1E1E2E";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <Icon className="w-5 h-5 mb-3" style={{ color: ACCENT }} />
                  <h4
                    className="text-sm font-semibold mb-2"
                    style={{ color: "#F5F5F7" }}
                  >
                    {d.name}
                  </h4>
                  <p className="text-xs leading-relaxed" style={{ color: "#8B8B9E" }}>
                    {d.desc}
                  </p>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </Section>

      {/* ============================================================ */}
      {/*  ARCHITECTURE                                                  */}
      {/* ============================================================ */}
      <Section id="architecture">
        <FadeIn>
          <SectionLabel>Architecture</SectionLabel>
          <SectionTitle>End-to-End Data Flow</SectionTitle>
          <p className="text-base leading-relaxed max-w-3xl mb-12" style={{ color: "#8B8B9E" }}>
            From agent event ingestion to kill-switch execution in under 50ms.
            The detection engine runs all 8 analyzers in parallel, scoring
            confidence before making automated decisions.
          </p>
        </FadeIn>
        <FadeIn delay={0.2}>
          <div
            className="rounded-2xl p-8 border overflow-hidden"
            style={{ background: SURFACE, borderColor: "#1E1E2E" }}
          >
            <ArchitectureDiagram />
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  COMPETITIVE LANDSCAPE                                         */}
      {/* ============================================================ */}
      <Section id="competitive" className="border-t" style={{ borderColor: "#1E1E2E" } as React.CSSProperties}>
        <FadeIn>
          <SectionLabel>Competitive Landscape</SectionLabel>
          <SectionTitle>The Only Real-Time Kill-Switch</SectionTitle>
          <p className="text-base leading-relaxed max-w-3xl" style={{ color: "#8B8B9E" }}>
            Existing tools observe and alert. AgentBreaker observes, detects, and
            kills — automatically, in real-time, with 8-dimensional confidence
            scoring.
          </p>
        </FadeIn>

        <FadeIn delay={0.2}>
          <div className="mt-12 overflow-x-auto">
            <table className="w-full text-sm" style={{ minWidth: 700 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #1E1E2E" }}>
                  {[
                    "Platform",
                    "Real-Time Kill",
                    "Semantic Detection",
                    "Dimensions",
                    "Cost Tracking",
                    "Self-Hosted",
                    "Pricing",
                  ].map((h) => (
                    <th
                      key={h}
                      className="py-4 px-3 text-left font-semibold text-xs tracking-wider uppercase"
                      style={{ color: "#8B8B9E" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {competitors.map((c, i) => {
                  const isUs = c.name === "AgentBreaker";
                  return (
                    <tr
                      key={c.name}
                      className="transition-colors"
                      style={{
                        borderBottom: "1px solid #1E1E2E",
                        background: isUs ? `${ACCENT}08` : "transparent",
                      }}
                    >
                      <td className="py-4 px-3 font-semibold" style={{ color: isUs ? ACCENT : "#F5F5F7" }}>
                        {c.name}
                      </td>
                      <td className="py-4 px-3">
                        <FeatureIcon val={c.realTimeKill} />
                      </td>
                      <td className="py-4 px-3">
                        <FeatureIcon val={c.semanticDetection} />
                      </td>
                      <td
                        className="py-4 px-3 text-center font-mono font-bold"
                        style={{ color: isUs ? ACCENT : "#8B8B9E" }}
                      >
                        {c.dimensions}
                      </td>
                      <td className="py-4 px-3">
                        <FeatureIcon val={c.costTracking} />
                      </td>
                      <td className="py-4 px-3">
                        <FeatureIcon val={c.selfHosted} />
                      </td>
                      <td className="py-4 px-3" style={{ color: "#8B8B9E" }}>
                        {c.pricing}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  TRACTION                                                      */}
      {/* ============================================================ */}
      <Section id="traction">
        <FadeIn>
          <SectionLabel>Traction</SectionLabel>
          <SectionTitle>Early Momentum</SectionTitle>
          <p
            className="text-xs italic mb-8"
            style={{ color: "#8B8B9E" }}
          >
            * Illustrative data for demonstration purposes
          </p>
        </FadeIn>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            {
              counter: agentsProtected,
              suffix: "",
              label: "Agents Protected",
              icon: Shield,
              color: ACCENT,
            },
            {
              counter: organizations,
              suffix: "",
              label: "Organizations",
              icon: Users,
              color: PURPLE,
            },
            {
              counter: savedMillions,
              suffix: "",
              label: "Saved ($M)",
              prefix: "$",
              decimal: true,
              icon: DollarSign,
              color: SUCCESS,
            },
            {
              counter: uptime,
              suffix: "%",
              label: "Uptime",
              decimal: true,
              icon: Clock,
              color: ACCENT,
            },
          ].map((item, i) => {
            const Icon = item.icon;
            const displayVal =
              "decimal" in item && item.decimal
                ? item.label === "Uptime"
                  ? (item.counter.value / 100).toFixed(2)
                  : (item.counter.value / 10).toFixed(1)
                : item.counter.value.toLocaleString();
            return (
              <FadeIn key={item.label} delay={i * 0.1}>
                <div
                  className="rounded-2xl p-8 border text-center"
                  style={{ background: SURFACE, borderColor: "#1E1E2E" }}
                >
                  <Icon
                    className="w-6 h-6 mx-auto mb-4"
                    style={{ color: item.color }}
                  />
                  <div className="text-4xl font-bold mb-2" style={{ color: "#F5F5F7" }}>
                    <span ref={item.counter.ref}>
                      {"prefix" in item ? item.prefix : ""}
                      {displayVal}
                      {item.suffix}
                    </span>
                  </div>
                  <p className="text-sm" style={{ color: "#8B8B9E" }}>
                    {item.label}
                  </p>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </Section>

      {/* ============================================================ */}
      {/*  BUSINESS MODEL                                                */}
      {/* ============================================================ */}
      <Section id="pricing" className="border-t" style={{ borderColor: "#1E1E2E" } as React.CSSProperties}>
        <FadeIn>
          <SectionLabel>Business Model</SectionLabel>
          <SectionTitle>Usage-Based SaaS Pricing</SectionTitle>
          <p className="text-base leading-relaxed max-w-3xl" style={{ color: "#8B8B9E" }}>
            Tiered pricing that scales with agent count. Enterprise tier includes
            dedicated support, custom detection rules, and on-premise deployment.
          </p>
        </FadeIn>

        <div className="grid md:grid-cols-3 gap-6 mt-12">
          <PricingCard
            tier="Starter"
            price="\u20AC199"
            agents="Up to 25 agents"
            features={[
              "8D detection engine",
              "Real-time dashboard",
              "Email alerts",
              "5 kill-switch rules",
              "7-day log retention",
              "Community support",
            ]}
          />
          <PricingCard
            tier="Growth"
            price="\u20AC999"
            agents="Up to 200 agents"
            highlighted
            features={[
              "Everything in Starter",
              "WebSocket kill-switch",
              "Custom detection thresholds",
              "Unlimited rules",
              "30-day log retention",
              "Slack & Teams integration",
              "Priority support",
            ]}
          />
          <PricingCard
            tier="Enterprise"
            price="\u20AC4,999"
            agents="Unlimited agents"
            features={[
              "Everything in Growth",
              "On-premise deployment",
              "Custom ML models",
              "SSO / SAML",
              "90-day log retention",
              "Dedicated CSM",
              "SLA guarantee",
              "Audit logs & compliance",
            ]}
          />
        </div>
      </Section>

      {/* ============================================================ */}
      {/*  TEAM                                                          */}
      {/* ============================================================ */}
      <Section id="team">
        <FadeIn>
          <SectionLabel>Team</SectionLabel>
          <SectionTitle>Built by Engineers Who Ship</SectionTitle>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div
            className="mt-12 rounded-2xl p-10 border text-center"
            style={{ background: SURFACE, borderColor: "#1E1E2E" }}
          >
            <div
              className="w-24 h-24 rounded-full mx-auto mb-6 flex items-center justify-center text-3xl font-bold"
              style={{ background: `linear-gradient(135deg, ${ACCENT}, ${PURPLE})`, color: BG }}
            >
              F
            </div>
            <h3 className="text-xl font-bold mb-1" style={{ color: "#F5F5F7" }}>
              Founder
            </h3>
            <p className="text-sm mb-4" style={{ color: ACCENT }}>
              CEO & CTO
            </p>
            <p
              className="text-sm leading-relaxed max-w-lg mx-auto"
              style={{ color: "#8B8B9E" }}
            >
              Deep expertise in AI systems, distributed architectures, and
              real-time monitoring. Building the infrastructure layer that
              makes autonomous AI agents safe for enterprise adoption.
            </p>
            <div className="mt-6 flex justify-center gap-8 text-xs" style={{ color: "#8B8B9E" }}>
              <span>Full-stack engineering</span>
              <span className="opacity-30">|</span>
              <span>AI/ML systems</span>
              <span className="opacity-30">|</span>
              <span>Enterprise SaaS</span>
            </div>
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  THE ASK                                                       */}
      {/* ============================================================ */}
      <Section id="ask" className="border-t" style={{ borderColor: "#1E1E2E" } as React.CSSProperties}>
        <FadeIn>
          <SectionLabel>The Ask</SectionLabel>
          <SectionTitle>Strategic Partnership or Series A</SectionTitle>
        </FadeIn>

        <div className="grid md:grid-cols-2 gap-8 mt-12">
          <FadeIn delay={0.1}>
            <div
              className="rounded-2xl p-8 border h-full"
              style={{ background: SURFACE, borderColor: "#1E1E2E" }}
            >
              <h3 className="text-lg font-semibold mb-6" style={{ color: "#F5F5F7" }}>
                Valuation Basis
              </h3>
              <div className="space-y-4 text-sm" style={{ color: "#8B8B9E" }}>
                <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "#1E1E2E" }}>
                  <span>Target Valuation</span>
                  <span className="font-bold text-lg" style={{ color: ACCENT }}>
                    \u20AC25\u201335M
                  </span>
                </div>
                <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "#1E1E2E" }}>
                  <span>Comparable: JetStream Security (Seed)</span>
                  <span className="font-semibold" style={{ color: "#F5F5F7" }}>$34M</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "#1E1E2E" }}>
                  <span>Comparable: Galileo AI (Series A)</span>
                  <span className="font-semibold" style={{ color: "#F5F5F7" }}>$18M</span>
                </div>
                <div className="flex justify-between items-center py-3">
                  <span>Market Category</span>
                  <span className="font-semibold" style={{ color: "#F5F5F7" }}>
                    AI Agent Infrastructure
                  </span>
                </div>
              </div>
            </div>
          </FadeIn>

          <FadeIn delay={0.2}>
            <div
              className="rounded-2xl p-8 border h-full"
              style={{ background: SURFACE, borderColor: "#1E1E2E" }}
            >
              <h3 className="text-lg font-semibold mb-6" style={{ color: "#F5F5F7" }}>
                What We&rsquo;re Looking For
              </h3>
              <ul className="space-y-4">
                {[
                  {
                    title: "Strategic Acquisition",
                    desc: "Integration into existing cloud/AI platform as a native safety layer.",
                  },
                  {
                    title: "Series A Lead",
                    desc: "Institutional investor with enterprise SaaS portfolio and AI thesis.",
                  },
                  {
                    title: "Design Partnership",
                    desc: "Fortune 500 co-development deal with production deployment commitment.",
                  },
                ].map((item) => (
                  <li key={item.title} className="flex gap-3">
                    <ChevronRight
                      className="w-5 h-5 mt-0.5 shrink-0"
                      style={{ color: ACCENT }}
                    />
                    <div>
                      <p className="text-sm font-semibold" style={{ color: "#F5F5F7" }}>
                        {item.title}
                      </p>
                      <p className="text-xs mt-1" style={{ color: "#8B8B9E" }}>
                        {item.desc}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </FadeIn>
        </div>
      </Section>

      {/* ============================================================ */}
      {/*  CONTACT FORM                                                  */}
      {/* ============================================================ */}
      <Section id="contact">
        <FadeIn>
          <SectionLabel>Get in Touch</SectionLabel>
          <SectionTitle>Start a Conversation</SectionTitle>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div className="max-w-xl mx-auto mt-12">
            {submitted ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-2xl p-12 border text-center"
                style={{ background: SURFACE, borderColor: `${SUCCESS}40` }}
              >
                <Check className="w-12 h-12 mx-auto mb-4" style={{ color: SUCCESS }} />
                <h3 className="text-xl font-bold mb-2" style={{ color: "#F5F5F7" }}>
                  Message Received
                </h3>
                <p className="text-sm" style={{ color: "#8B8B9E" }}>
                  We&rsquo;ll be in touch within 24 hours.
                </p>
              </motion.div>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="rounded-2xl p-8 border space-y-6"
                style={{ background: SURFACE, borderColor: "#1E1E2E" }}
              >
                <div>
                  <label
                    className="block text-xs font-semibold mb-2 tracking-wide uppercase"
                    style={{ color: "#8B8B9E" }}
                  >
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-colors border"
                    style={{
                      background: BG,
                      borderColor: "#1E1E2E",
                      color: "#F5F5F7",
                    }}
                    onFocus={(e) => (e.currentTarget.style.borderColor = `${ACCENT}60`)}
                    onBlur={(e) => (e.currentTarget.style.borderColor = "#1E1E2E")}
                    placeholder="Your name"
                  />
                </div>
                <div>
                  <label
                    className="block text-xs font-semibold mb-2 tracking-wide uppercase"
                    style={{ color: "#8B8B9E" }}
                  >
                    Email
                  </label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-colors border"
                    style={{
                      background: BG,
                      borderColor: "#1E1E2E",
                      color: "#F5F5F7",
                    }}
                    onFocus={(e) => (e.currentTarget.style.borderColor = `${ACCENT}60`)}
                    onBlur={(e) => (e.currentTarget.style.borderColor = "#1E1E2E")}
                    placeholder="investor@firm.com"
                  />
                </div>
                <div>
                  <label
                    className="block text-xs font-semibold mb-2 tracking-wide uppercase"
                    style={{ color: "#8B8B9E" }}
                  >
                    Message
                  </label>
                  <textarea
                    required
                    rows={4}
                    value={formData.message}
                    onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-colors border resize-none"
                    style={{
                      background: BG,
                      borderColor: "#1E1E2E",
                      color: "#F5F5F7",
                    }}
                    onFocus={(e) => (e.currentTarget.style.borderColor = `${ACCENT}60`)}
                    onBlur={(e) => (e.currentTarget.style.borderColor = "#1E1E2E")}
                    placeholder="Tell us about your interest..."
                  />
                </div>
                <button
                  type="submit"
                  className="w-full py-3.5 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-200"
                  style={{ background: ACCENT, color: BG }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.9")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                >
                  <Send className="w-4 h-4" />
                  Send Message
                </button>
              </form>
            )}
          </div>
        </FadeIn>
      </Section>

      {/* ============================================================ */}
      {/*  FOOTER                                                        */}
      {/* ============================================================ */}
      <footer
        className="py-12 px-6 text-center border-t"
        style={{ borderColor: "#1E1E2E" }}
      >
        <p className="text-xs" style={{ color: "#8B8B9E" }}>
          Confidential. For intended recipients only. AgentBreaker &copy; {new Date().getFullYear()}
        </p>
      </footer>
    </div>
  );
}
