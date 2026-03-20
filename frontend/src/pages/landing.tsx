import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { Code, Activity, ShieldCheck, Check, ArrowRight, Copy } from "lucide-react";
import { Link } from "react-router-dom";

/* ------------------------------------------------------------------ */
/*  Animated counter hook                                              */
/* ------------------------------------------------------------------ */
function useCountUp(end: number, duration = 2000, startOnView = true) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const started = useRef(false);

  useEffect(() => {
    if (!startOnView || !inView || started.current) return;
    started.current = true;
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * end));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView, end, duration, startOnView]);

  return { value, ref };
}

/* ------------------------------------------------------------------ */
/*  Fade-in animation wrapper                                          */
/* ------------------------------------------------------------------ */
const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: { opacity: 1, y: 0 },
};

function FadeIn({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
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
/*  Copy button for code snippets                                      */
/* ------------------------------------------------------------------ */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Section divider                                                    */
/* ------------------------------------------------------------------ */
function Divider() {
  return (
    <div className="w-full max-w-6xl mx-auto px-6">
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  );
}

/* ================================================================== */
/*  HERO                                                               */
/* ================================================================== */
function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Grid background */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />
      {/* Radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-accent/[0.03] rounded-full blur-[120px] pointer-events-none" />

      <div className="relative z-10 max-w-6xl mx-auto px-6 text-center">
        <FadeIn>
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-full border border-border text-xs text-text-muted bg-surface/50 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            Now in public beta
          </div>
        </FadeIn>

        <FadeIn delay={0.1}>
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-text-primary max-w-3xl mx-auto leading-[1.1] tracking-tight">
            Stop burning money on runaway AI&nbsp;agents.
          </h1>
        </FadeIn>

        <FadeIn delay={0.2}>
          <p className="mt-6 text-xl md:text-2xl text-text-muted font-medium">
            Detect loops. Kill waste. Save budget.
          </p>
        </FadeIn>

        <FadeIn delay={0.3}>
          <p className="mt-5 text-text-muted max-w-2xl mx-auto leading-relaxed">
            Real-time semantic analysis detects when your AI agents spiral&nbsp;&mdash;
            infinite&nbsp;loops, circular reasoning, diminishing returns&nbsp;&mdash;
            and kills them automatically.
          </p>
        </FadeIn>

        <FadeIn delay={0.4}>
          <div className="mt-10 flex flex-col items-center gap-4">
            <Link
              to="/login"
              className="group inline-flex items-center gap-2 px-8 py-3.5 bg-accent text-background font-semibold rounded-lg text-base shadow-[0_0_32px_rgba(0,212,255,0.15)] hover:shadow-[0_0_48px_rgba(0,212,255,0.25)] hover:brightness-110 transition-all duration-300"
            >
              Start Free
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <p className="text-xs text-text-muted">
              No credit card required&ensp;&middot;&ensp;50 agents free
            </p>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  STATS                                                              */
/* ================================================================== */
function Stats() {
  const stats = [
    { end: 400, prefix: "", suffix: "M €", label: "Lost by Fortune 500 on runaway agents" },
    { end: 73, prefix: "", suffix: "%", label: "Of enterprise agent deployments exceed budget" },
    { end: 85, prefix: "", suffix: "%", label: "Of AI budgets go to inference costs" },
    { end: 40, prefix: "", suffix: "%", label: "Of agent projects canceled by 2027" },
  ];

  return (
    <section className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-4">
          {stats.map((s, i) => {
            const counter = useCountUp(s.end, 2200);
            return (
              <FadeIn key={i} delay={i * 0.1} className="text-center">
                <span
                  ref={counter.ref}
                  className="block font-mono text-4xl md:text-5xl font-bold text-accent"
                >
                  {s.prefix}
                  {counter.value}
                  {s.suffix}
                </span>
                <span className="mt-2 block text-sm text-text-muted max-w-[200px] mx-auto leading-snug">
                  {s.label}
                </span>
              </FadeIn>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  HOW IT WORKS                                                       */
/* ================================================================== */
function HowItWorks() {
  const steps = [
    {
      icon: Code,
      title: "Install",
      desc: "Add 3 lines of Python. Works with LangChain, CrewAI, AutoGen.",
    },
    {
      icon: Activity,
      title: "Monitor",
      desc: "5 detection dimensions analyze every step in real-time. No hard caps.",
    },
    {
      icon: ShieldCheck,
      title: "Auto-Kill",
      desc: "Automatic kill when agents spiral. Cost and impact reported instantly.",
    },
  ];

  return (
    <section className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary text-center">
            How AgentBreaker Works
          </h2>
        </FadeIn>

        <div className="mt-16 grid md:grid-cols-3 gap-12 md:gap-8">
          {steps.map((s, i) => (
            <FadeIn key={i} delay={i * 0.15} className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-5">
                <s.icon className="w-6 h-6 text-accent" />
              </div>
              <h3 className="text-lg font-bold text-text-primary">{s.title}</h3>
              <p className="mt-2 text-text-muted leading-relaxed max-w-xs">{s.desc}</p>
            </FadeIn>
          ))}
        </div>

        {/* Connector line (desktop) */}
        <div className="hidden md:block relative -mt-[7.5rem] mb-[5rem] mx-auto" style={{ maxWidth: "66%" }}>
          <div className="h-px bg-gradient-to-r from-accent/0 via-accent/20 to-accent/0" />
        </div>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  CODE                                                               */
/* ================================================================== */
function CodeSection() {
  const pipCmd = "pip install agentbreaker";

  return (
    <section className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary text-center">
            Built for Engineers
          </h2>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div className="mt-12 max-w-2xl mx-auto">
            {/* Code block */}
            <div className="rounded-xl border border-border overflow-hidden bg-[#0D1117]">
              {/* Title bar */}
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface/40">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-danger/60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-warning/60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-success/60" />
                </div>
                <span className="text-xs text-text-muted font-mono">agent.py</span>
                <CopyButton
                  text={`from agentbreaker import AgentBreaker

ab = AgentBreaker(api_key="ab_live_xxx")

result = ab.track_step(
    agent_id="my-agent",
    input=prompt,
    output=response,
    tokens=150,
    cost=0.003
)
# result.action == "kill" when spiral detected`}
                />
              </div>

              {/* Code */}
              <pre className="px-5 py-5 text-sm leading-relaxed font-mono overflow-x-auto">
                <code>
                  <span className="text-purple">from</span>
                  <span className="text-text-primary"> agentbreaker </span>
                  <span className="text-purple">import</span>
                  <span className="text-text-primary"> AgentBreaker{"\n"}</span>
                  {"\n"}
                  <span className="text-text-primary">ab = </span>
                  <span className="text-accent">AgentBreaker</span>
                  <span className="text-text-muted">(</span>
                  <span className="text-text-primary">api_key=</span>
                  <span className="text-success">"ab_live_xxx"</span>
                  <span className="text-text-muted">){"\n"}</span>
                  {"\n"}
                  <span className="text-text-primary">result = ab.</span>
                  <span className="text-accent">track_step</span>
                  <span className="text-text-muted">(</span>
                  {"\n"}
                  <span className="text-text-primary">{"    "}agent_id=</span>
                  <span className="text-success">"my-agent"</span>
                  <span className="text-text-muted">,{"\n"}</span>
                  <span className="text-text-primary">{"    "}input=</span>
                  <span className="text-text-primary">prompt</span>
                  <span className="text-text-muted">,{"\n"}</span>
                  <span className="text-text-primary">{"    "}output=</span>
                  <span className="text-text-primary">response</span>
                  <span className="text-text-muted">,{"\n"}</span>
                  <span className="text-text-primary">{"    "}tokens=</span>
                  <span className="text-warning">150</span>
                  <span className="text-text-muted">,{"\n"}</span>
                  <span className="text-text-primary">{"    "}cost=</span>
                  <span className="text-warning">0.003</span>
                  {"\n"}
                  <span className="text-text-muted">){"\n"}</span>
                  <span className="text-text-muted">{"# "}result.action == "kill" when spiral detected</span>
                </code>
              </pre>
            </div>

            {/* Pip install badge */}
            <div className="mt-6 flex items-center justify-center">
              <div className="inline-flex items-center gap-3 px-4 py-2 rounded-lg border border-border bg-surface/60 font-mono text-sm text-text-primary">
                <span className="text-text-muted select-none">$</span>
                {pipCmd}
                <CopyButton text={pipCmd} />
              </div>
            </div>

            <p className="mt-4 text-center text-sm text-text-muted">
              Works with LangChain, CrewAI, AutoGen, Azure AI Agents
            </p>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  PRICING                                                            */
/* ================================================================== */
interface PlanProps {
  name: string;
  price: string;
  period?: string;
  badge?: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
  delay?: number;
}

function PlanCard({ name, price, period, badge, features, cta, highlighted, delay = 0 }: PlanProps) {
  return (
    <FadeIn delay={delay}>
      <div
        className={`relative flex flex-col rounded-2xl border p-8 h-full transition-colors ${
          highlighted
            ? "border-accent/40 bg-accent/[0.03] shadow-[0_0_48px_rgba(0,212,255,0.06)]"
            : "border-border bg-surface/40 hover:border-border-hover"
        }`}
      >
        {badge && (
          <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-semibold bg-accent text-background">
            {badge}
          </span>
        )}

        <h3 className="text-lg font-bold text-text-primary">{name}</h3>
        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-4xl font-bold font-mono text-text-primary">{price}</span>
          {period && <span className="text-text-muted text-sm">{period}</span>}
        </div>

        <ul className="mt-8 flex flex-col gap-3 flex-1">
          {features.map((f, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-text-muted">
              <Check className="w-4 h-4 mt-0.5 text-accent shrink-0" />
              {f}
            </li>
          ))}
        </ul>

        <Link
          to={cta === "Contact Sales" ? "#" : "/login"}
          className={`mt-8 flex items-center justify-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold transition-all duration-200 ${
            highlighted
              ? "bg-accent text-background hover:brightness-110 shadow-[0_0_24px_rgba(0,212,255,0.12)]"
              : "border border-border text-text-primary hover:bg-surface-hover hover:border-border-hover"
          }`}
        >
          {cta}
        </Link>
      </div>
    </FadeIn>
  );
}

function Pricing() {
  return (
    <section className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary text-center">
            Simple, transparent pricing
          </h2>
        </FadeIn>

        <div className="mt-14 grid md:grid-cols-3 gap-6">
          <PlanCard
            name="Starter"
            price="199 €"
            period="/mo"
            features={[
              "3 projects, 50 agents",
              "Email alerts",
              "Community support",
            ]}
            cta="Start Free"
            delay={0.1}
          />
          <PlanCard
            name="Growth"
            price="999 €"
            period="/mo"
            badge="Most Popular"
            highlighted
            features={[
              "10 projects, 500 agents",
              "Slack + PagerDuty integrations",
              "Priority support",
              "Carbon impact reports",
            ]}
            cta="Start Trial"
            delay={0.2}
          />
          <PlanCard
            name="Enterprise"
            price="Contact Sales"
            features={[
              "Unlimited projects & agents",
              "SSO + SAML",
              "Dedicated CSM + SLA",
              "Custom integrations",
              "Advanced analytics",
            ]}
            cta="Contact Sales"
            delay={0.3}
          />
        </div>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  FOOTER                                                             */
/* ================================================================== */
function Footer() {
  const links = [
    { label: "Documentation", href: "#" },
    { label: "API Reference", href: "#" },
    { label: "GitHub", href: "#" },
    { label: "Pricing", href: "#" },
  ];

  return (
    <footer className="border-t border-border py-12">
      <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6 text-sm text-text-muted">
        <div className="flex items-center gap-6">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="hover:text-text-primary transition-colors"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex flex-col items-center md:items-end gap-1 text-xs">
          <span>Built for responsible AI.</span>
          <span>&copy; 2026 AgentBreaker</span>
        </div>
      </div>
    </footer>
  );
}

/* ================================================================== */
/*  NAV                                                                */
/* ================================================================== */
function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-background/80 backdrop-blur-xl border-b border-border"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/landing" className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-accent" />
          </div>
          <span className="font-bold text-text-primary text-lg tracking-tight">AgentBreaker</span>
        </Link>

        <div className="flex items-center gap-6">
          <a href="#pricing" className="hidden md:block text-sm text-text-muted hover:text-text-primary transition-colors">
            Pricing
          </a>
          <Link to="/roi" className="hidden md:block text-sm text-text-muted hover:text-text-primary transition-colors">
            ROI Calculator
          </Link>
          <a href="#" className="hidden md:block text-sm text-text-muted hover:text-text-primary transition-colors">
            Docs
          </a>
          <Link
            to="/login"
            className="text-sm font-medium text-text-primary hover:text-accent transition-colors"
          >
            Sign in
          </Link>
          <Link
            to="/login"
            className="px-4 py-2 bg-accent text-background text-sm font-semibold rounded-lg hover:brightness-110 transition-all"
          >
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  );
}

/* ================================================================== */
/*  USE CASES                                                          */
/* ================================================================== */
function UseCases() {
  const cases = [
    {
      industry: "Financial Services",
      title: "Fraud detection agents burning $47K/day in loops",
      result: "83% cost reduction",
      detail: "A top-10 bank deployed 200+ fraud-detection agents that frequently entered semantic loops when encountering novel transaction patterns. AgentBreaker detected and killed 1,847 runaway sessions in the first month, saving $1.4M in wasted inference.",
      metric: "$1.4M saved in 30 days",
    },
    {
      industry: "Healthcare",
      title: "Clinical note summarizers hitting context limits",
      result: "94% fewer incidents",
      detail: "A health-tech company running clinical note summarization agents saw context inflation blow up costs. AgentBreaker's context inflation detector caught bloat patterns 12 steps earlier than their hard token caps.",
      metric: "12 steps earlier detection",
    },
    {
      industry: "Developer Tools",
      title: "Code review bots stuck in circular reasoning",
      result: "99.7% uptime",
      detail: "An enterprise DevOps platform with 500 concurrent code-review agents used AgentBreaker's reasoning loop detector to catch circular suggestion patterns that previously required manual intervention.",
      metric: "500 agents monitored 24/7",
    },
  ];

  return (
    <section className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary text-center">
            Real results from real deployments
          </h2>
          <p className="mt-4 text-text-muted text-center max-w-2xl mx-auto">
            AgentBreaker protects production AI agents across finance, healthcare, and developer platforms.
          </p>
        </FadeIn>

        <div className="mt-14 grid md:grid-cols-3 gap-6">
          {cases.map((c, i) => (
            <FadeIn key={i} delay={i * 0.12}>
              <div className="flex flex-col rounded-2xl border border-border bg-surface/40 p-7 h-full hover:border-border-hover transition-colors">
                <span className="text-xs font-semibold text-accent uppercase tracking-wider">
                  {c.industry}
                </span>
                <h3 className="mt-3 text-lg font-bold text-text-primary leading-snug">
                  {c.title}
                </h3>
                <p className="mt-3 text-sm text-text-muted leading-relaxed flex-1">
                  {c.detail}
                </p>
                <div className="mt-5 pt-5 border-t border-border flex items-center justify-between">
                  <span className="text-sm font-semibold text-success">{c.result}</span>
                  <span className="text-xs font-mono text-text-muted">{c.metric}</span>
                </div>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  ENTERPRISE FEATURES                                                */
/* ================================================================== */
function EnterpriseFeatures() {
  const features = [
    { title: "SOC 2 Type II Ready", desc: "Audit logs, encryption at rest, RBAC with org-scoped multi-tenancy." },
    { title: "Carbon Impact Reports", desc: "Track CO2 avoided per kill. ESG-ready metrics for sustainability reporting." },
    { title: "8 Detection Dimensions", desc: "Semantic similarity, reasoning loops, goal drift, entropy, error cascades, cost velocity, context inflation, diminishing returns." },
    { title: "Sub-200ms Latency", desc: "Detection runs in the agent's hot path without slowing execution. Zero-overhead on healthy agents." },
    { title: "LangChain / CrewAI / AutoGen", desc: "Native callbacks for major frameworks. 3 lines of code to integrate." },
    { title: "Slack / PagerDuty / Webhooks", desc: "Alert your team instantly when agents are killed. Full incident forensics in the dashboard." },
  ];

  return (
    <section className="py-24 md:py-32 bg-surface/20">
      <div className="max-w-6xl mx-auto px-6">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary text-center">
            Enterprise-grade from day one
          </h2>
        </FadeIn>

        <div className="mt-14 grid md:grid-cols-3 gap-6">
          {features.map((f, i) => (
            <FadeIn key={i} delay={i * 0.08}>
              <div className="p-6 rounded-xl border border-border bg-background/50 h-full">
                <h3 className="text-base font-bold text-text-primary">{f.title}</h3>
                <p className="mt-2 text-sm text-text-muted leading-relaxed">{f.desc}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  CTA                                                                */
/* ================================================================== */
function FinalCTA() {
  return (
    <section className="py-24 md:py-32">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <FadeIn>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary">
            Stop losing money to runaway agents.
          </h2>
          <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
            Join the companies already saving millions with real-time AI agent governance.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-8 py-3.5 bg-accent text-background font-semibold rounded-lg text-base shadow-[0_0_32px_rgba(0,212,255,0.15)] hover:shadow-[0_0_48px_rgba(0,212,255,0.25)] hover:brightness-110 transition-all duration-300"
            >
              Start Free Trial
              <ArrowRight className="w-4 h-4" />
            </Link>
            <a
              href="mailto:sales@agentbreaker.com"
              className="inline-flex items-center gap-2 px-8 py-3.5 border border-border text-text-primary font-semibold rounded-lg text-base hover:bg-surface-hover hover:border-border-hover transition-all duration-200"
            >
              Talk to Sales
            </a>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

/* ================================================================== */
/*  LANDING PAGE                                                       */
/* ================================================================== */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-text-primary">
      <Nav />
      <Hero />
      <Divider />
      <Stats />
      <Divider />
      <HowItWorks />
      <Divider />
      <CodeSection />
      <Divider />
      <UseCases />
      <Divider />
      <EnterpriseFeatures />
      <Divider />
      <div id="pricing">
        <Pricing />
      </div>
      <Divider />
      <FinalCTA />
      <Footer />
    </div>
  );
}
