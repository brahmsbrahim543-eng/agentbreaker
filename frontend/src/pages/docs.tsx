import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import {
  Book,
  Download,
  Settings,
  Radar,
  Server,
  Code2,
  Radio,
  AlertTriangle,
  CreditCard,
  Copy,
  Check,
  ChevronRight,
  ArrowLeft,
  ExternalLink,
  Zap,
  Search,
  Menu,
  X,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface Section {
  id: string;
  label: string;
  icon: React.ReactNode;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const SECTIONS: Section[] = [
  { id: "quickstart", label: "Quickstart", icon: <Zap size={16} /> },
  { id: "installation", label: "Installation", icon: <Download size={16} /> },
  { id: "configuration", label: "Configuration", icon: <Settings size={16} /> },
  { id: "detection-dimensions", label: "Detection Dimensions", icon: <Radar size={16} /> },
  { id: "api-reference", label: "API Reference", icon: <Server size={16} /> },
  { id: "sdk-reference", label: "SDK Reference", icon: <Code2 size={16} /> },
  { id: "websocket-events", label: "WebSocket Events", icon: <Radio size={16} /> },
  { id: "incident-types", label: "Incident Types", icon: <AlertTriangle size={16} /> },
  { id: "rate-limits-pricing", label: "Rate Limits & Pricing", icon: <CreditCard size={16} /> },
];

/* ------------------------------------------------------------------ */
/*  Code Block with Copy                                               */
/* ------------------------------------------------------------------ */
function CodeBlock({
  code,
  language = "python",
  title,
}: {
  code: string;
  language?: string;
  title?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [code]);

  return (
    <div className="group relative rounded-lg border border-white/[0.06] bg-[#0D0D14] overflow-hidden my-4">
      {title && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.06] bg-white/[0.02]">
          <span className="text-xs font-mono text-[#8B8B9E]">{title}</span>
          <span className="text-xs font-mono text-[#8B8B9E] uppercase">{language}</span>
        </div>
      )}
      <div className="relative">
        <pre className="p-4 overflow-x-auto text-sm leading-relaxed font-mono">
          <code>
            <SyntaxHighlight code={code} language={language} />
          </code>
        </pre>
        <button
          onClick={handleCopy}
          className="absolute top-3 right-3 p-1.5 rounded-md bg-white/[0.05] border border-white/[0.08] opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/[0.1] cursor-pointer"
          aria-label="Copy code"
        >
          {copied ? (
            <Check size={14} className="text-[#10B981]" />
          ) : (
            <Copy size={14} className="text-[#8B8B9E]" />
          )}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Minimal Syntax Highlighting                                        */
/* ------------------------------------------------------------------ */
function SyntaxHighlight({ code, language }: { code: string; language: string }) {
  if (language === "json") return <JsonHighlight code={code} />;
  if (language === "bash" || language === "shell") return <BashHighlight code={code} />;
  return <PythonHighlight code={code} />;
}

function PythonHighlight({ code }: { code: string }) {
  const keywords =
    /\b(import|from|def|class|return|if|elif|else|for|while|with|as|try|except|finally|raise|yield|async|await|True|False|None|and|or|not|in|is|lambda|pass|break|continue)\b/g;
  const strings = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
  const comments = /(#.*$)/gm;
  const decorators = /(@\w+)/g;
  const functions = /\b(\w+)(?=\()/g;
  const numbers = /\b(\d+\.?\d*)\b/g;

  const parts: { start: number; end: number; cls: string }[] = [];

  const collect = (regex: RegExp, cls: string) => {
    let m;
    const r = new RegExp(regex.source, regex.flags);
    while ((m = r.exec(code)) !== null) {
      parts.push({ start: m.index, end: m.index + m[0].length, cls });
    }
  };

  collect(comments, "text-[#6A737D]");
  collect(strings, "text-[#10B981]");
  collect(keywords, "text-[#A855F7]");
  collect(decorators, "text-[#F59E0B]");
  collect(functions, "text-[#00D4FF]");
  collect(numbers, "text-[#F59E0B]");

  // Sort by priority: comments > strings > rest; earlier start wins ties
  parts.sort((a, b) => a.start - b.start);

  // Remove overlaps
  const cleaned: typeof parts = [];
  let lastEnd = 0;
  for (const p of parts) {
    if (p.start >= lastEnd) {
      cleaned.push(p);
      lastEnd = p.end;
    }
  }

  const result: React.ReactNode[] = [];
  let cursor = 0;
  for (const p of cleaned) {
    if (cursor < p.start) {
      result.push(
        <span key={cursor} className="text-[#F5F5F7]">
          {code.slice(cursor, p.start)}
        </span>
      );
    }
    result.push(
      <span key={p.start} className={p.cls}>
        {code.slice(p.start, p.end)}
      </span>
    );
    cursor = p.end;
  }
  if (cursor < code.length) {
    result.push(
      <span key={cursor} className="text-[#F5F5F7]">
        {code.slice(cursor)}
      </span>
    );
  }

  return <>{result}</>;
}

function JsonHighlight({ code }: { code: string }) {
  const parts: React.ReactNode[] = [];
  const lines = code.split("\n");
  lines.forEach((line, i) => {
    const keyMatch = line.match(/^(\s*)"([^"]+)"(\s*:\s*)/);
    if (keyMatch) {
      const [, indent, key, colon] = keyMatch;
      const rest = line.slice(keyMatch[0].length);
      parts.push(
        <span key={`${i}-indent`} className="text-[#F5F5F7]">{indent}</span>,
        <span key={`${i}-q1`} className="text-[#10B981]">"</span>,
        <span key={`${i}-key`} className="text-[#00D4FF]">{key}</span>,
        <span key={`${i}-q2`} className="text-[#10B981]">"</span>,
        <span key={`${i}-colon`} className="text-[#F5F5F7]">{colon}</span>
      );
      // value
      const strVal = rest.match(/^"([^"]*)"(.*)/);
      const numVal = rest.match(/^(\d+\.?\d*)(.*)/);
      const boolVal = rest.match(/^(true|false|null)(.*)/);
      if (strVal) {
        parts.push(
          <span key={`${i}-val`} className="text-[#10B981]">"{strVal[1]}"</span>,
          <span key={`${i}-rest`} className="text-[#F5F5F7]">{strVal[2]}</span>
        );
      } else if (numVal) {
        parts.push(
          <span key={`${i}-val`} className="text-[#F59E0B]">{numVal[1]}</span>,
          <span key={`${i}-rest`} className="text-[#F5F5F7]">{numVal[2]}</span>
        );
      } else if (boolVal) {
        parts.push(
          <span key={`${i}-val`} className="text-[#A855F7]">{boolVal[1]}</span>,
          <span key={`${i}-rest`} className="text-[#F5F5F7]">{boolVal[2]}</span>
        );
      } else {
        parts.push(<span key={`${i}-val`} className="text-[#F5F5F7]">{rest}</span>);
      }
    } else {
      parts.push(<span key={i} className="text-[#F5F5F7]">{line}</span>);
    }
    if (i < lines.length - 1) parts.push(<br key={`br-${i}`} />);
  });
  return <>{parts}</>;
}

function BashHighlight({ code }: { code: string }) {
  const lines = code.split("\n");
  const result: React.ReactNode[] = [];
  lines.forEach((line, i) => {
    if (line.startsWith("#")) {
      result.push(<span key={i} className="text-[#6A737D]">{line}</span>);
    } else if (line.startsWith("$")) {
      result.push(
        <span key={`${i}-p`} className="text-[#10B981]">$ </span>,
        <span key={i} className="text-[#F5F5F7]">{line.slice(2)}</span>
      );
    } else {
      const cmdMatch = line.match(/^(\w+)(.*)/);
      if (cmdMatch) {
        result.push(
          <span key={`${i}-cmd`} className="text-[#00D4FF]">{cmdMatch[1]}</span>,
          <span key={i} className="text-[#F5F5F7]">{cmdMatch[2]}</span>
        );
      } else {
        result.push(<span key={i} className="text-[#F5F5F7]">{line}</span>);
      }
    }
    if (i < lines.length - 1) result.push(<br key={`br-${i}`} />);
  });
  return <>{result}</>;
}

/* ------------------------------------------------------------------ */
/*  Inline code                                                        */
/* ------------------------------------------------------------------ */
function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.06] text-[#00D4FF] text-sm font-mono">
      {children}
    </code>
  );
}

/* ------------------------------------------------------------------ */
/*  HTTP Method Badge                                                  */
/* ------------------------------------------------------------------ */
function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "bg-[#10B981]/15 text-[#10B981] border-[#10B981]/30",
    POST: "bg-[#00D4FF]/15 text-[#00D4FF] border-[#00D4FF]/30",
    PUT: "bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/30",
    DELETE: "bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/30",
    PATCH: "bg-[#A855F7]/15 text-[#A855F7] border-[#A855F7]/30",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-bold font-mono border ${colors[method] || colors.GET}`}
    >
      {method}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Step component for Quickstart                                      */
/* ------------------------------------------------------------------ */
function Step({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4 mb-8">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#00D4FF]/15 border border-[#00D4FF]/30 flex items-center justify-center text-[#00D4FF] text-sm font-bold">
        {number}
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-lg font-semibold text-[#F5F5F7] mb-2">{title}</h3>
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Detection Dimension Card                                           */
/* ------------------------------------------------------------------ */
function DimensionCard({
  name,
  description,
  howItWorks,
  weight,
  example,
  threshold,
}: {
  name: string;
  description: string;
  howItWorks: string;
  weight: string;
  example: string;
  threshold?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg border border-white/[0.06] bg-[#111118] overflow-hidden mb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-white/[0.02] transition-colors cursor-pointer"
      >
        <div>
          <h4 className="text-[#F5F5F7] font-semibold">{name}</h4>
          <p className="text-sm text-[#8B8B9E] mt-1">{description}</p>
        </div>
        <ChevronRight
          size={16}
          className={`text-[#8B8B9E] transition-transform flex-shrink-0 ml-4 ${expanded ? "rotate-90" : ""}`}
        />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-white/[0.06] pt-4 space-y-3">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-[#00D4FF]">
                  How it works
                </span>
                <p className="text-sm text-[#8B8B9E] mt-1">{howItWorks}</p>
              </div>
              {threshold && (
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-[#F59E0B]">
                    Default Threshold
                  </span>
                  <p className="text-sm text-[#8B8B9E] mt-1">{threshold}</p>
                </div>
              )}
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-[#A855F7]">
                  Weight in composite score
                </span>
                <p className="text-sm text-[#8B8B9E] mt-1">{weight}</p>
              </div>
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-[#10B981]">
                  Example scenario
                </span>
                <p className="text-sm text-[#8B8B9E] mt-1">{example}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Endpoint block for API Reference                                   */
/* ------------------------------------------------------------------ */
function Endpoint({
  method,
  path,
  description,
  requestBody,
  responseBody,
}: {
  method: string;
  path: string;
  description: string;
  requestBody?: string;
  responseBody: string;
}) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-[#111118] p-5 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <MethodBadge method={method} />
        <code className="text-sm font-mono text-[#F5F5F7]">{path}</code>
      </div>
      <p className="text-sm text-[#8B8B9E] mb-4">{description}</p>
      {requestBody && <CodeBlock code={requestBody} language="json" title="Request Body" />}
      <CodeBlock code={responseBody} language="json" title="Response" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Pricing Tier Card                                                  */
/* ------------------------------------------------------------------ */
function PricingCard({
  name,
  price,
  features,
  highlighted,
}: {
  name: string;
  price: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-5 ${
        highlighted
          ? "border-[#00D4FF]/40 bg-[#00D4FF]/[0.04]"
          : "border-white/[0.06] bg-[#111118]"
      }`}
    >
      <h4 className="text-lg font-semibold text-[#F5F5F7]">{name}</h4>
      <p className="text-2xl font-bold text-[#00D4FF] mt-2">{price}</p>
      <ul className="mt-4 space-y-2">
        {features.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-[#8B8B9E]">
            <Check size={14} className="text-[#10B981] mt-0.5 flex-shrink-0" />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Table component                                                    */
/* ------------------------------------------------------------------ */
function DocTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto my-4 rounded-lg border border-white/[0.06]">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-white/[0.03]">
            {headers.map((h, i) => (
              <th
                key={i}
                className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#8B8B9E] border-b border-white/[0.06]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-white/[0.04] last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-[#8B8B9E] font-mono text-xs">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Callout / Admonition                                               */
/* ------------------------------------------------------------------ */
function Callout({
  type = "info",
  children,
}: {
  type?: "info" | "warning" | "danger";
  children: React.ReactNode;
}) {
  const styles = {
    info: "border-[#00D4FF]/30 bg-[#00D4FF]/[0.04] text-[#00D4FF]",
    warning: "border-[#F59E0B]/30 bg-[#F59E0B]/[0.04] text-[#F59E0B]",
    danger: "border-[#EF4444]/30 bg-[#EF4444]/[0.04] text-[#EF4444]",
  };
  return (
    <div className={`rounded-lg border-l-4 p-4 my-4 ${styles[type]}`}>
      <p className="text-sm text-[#8B8B9E]">{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("quickstart");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const contentRef = useRef<HTMLDivElement>(null);

  /* ---------- scroll spy ---------- */
  useEffect(() => {
    const handleScroll = () => {
      const container = contentRef.current;
      if (!container) return;
      const scrollTop = container.scrollTop;
      let current = "quickstart";
      for (const section of SECTIONS) {
        const el = document.getElementById(section.id);
        if (el) {
          const top = el.offsetTop - container.offsetTop - 120;
          if (scrollTop >= top) current = section.id;
        }
      }
      setActiveSection(current);
    };
    const container = contentRef.current;
    container?.addEventListener("scroll", handleScroll, { passive: true });
    return () => container?.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    const container = contentRef.current;
    if (el && container) {
      const top = el.offsetTop - container.offsetTop - 40;
      container.scrollTo({ top, behavior: "smooth" });
    }
    setMobileNavOpen(false);
  };

  const filteredSections = searchQuery
    ? SECTIONS.filter((s) =>
        s.label.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : SECTIONS;

  return (
    <div className="flex h-screen bg-[#0A0A0F] text-[#F5F5F7] overflow-hidden">
      {/* ---- Mobile nav toggle ---- */}
      <button
        onClick={() => setMobileNavOpen(!mobileNavOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-[#111118] border border-white/[0.08] cursor-pointer"
      >
        {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* ---- Sidebar ---- */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-72 bg-[#0A0A0F] border-r border-white/[0.06] flex flex-col transition-transform lg:translate-x-0 ${
          mobileNavOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo / Header */}
        <div className="p-6 border-b border-white/[0.06]">
          <Link to="/" className="flex items-center gap-2 group">
            <ArrowLeft
              size={16}
              className="text-[#8B8B9E] group-hover:text-[#00D4FF] transition-colors"
            />
            <span className="text-sm text-[#8B8B9E] group-hover:text-[#00D4FF] transition-colors">
              Back to app
            </span>
          </Link>
          <div className="mt-4 flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D4FF] to-[#A855F7] flex items-center justify-center">
              <Book size={16} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-[#F5F5F7]">AgentBreaker</h1>
              <p className="text-xs text-[#8B8B9E]">Documentation</p>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="px-4 py-3">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8B8B9E]"
            />
            <input
              type="text"
              placeholder="Search docs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-white/[0.06] rounded-lg text-sm text-[#F5F5F7] placeholder:text-[#8B8B9E] outline-none focus:border-[#00D4FF]/40 transition-colors"
            />
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 pb-6">
          <ul className="space-y-0.5">
            {filteredSections.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => scrollTo(s.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all cursor-pointer ${
                    activeSection === s.id
                      ? "bg-[#00D4FF]/10 text-[#00D4FF] font-medium"
                      : "text-[#8B8B9E] hover:text-[#F5F5F7] hover:bg-white/[0.03]"
                  }`}
                >
                  {s.icon}
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/[0.06]">
          <div className="px-3 py-2 rounded-lg bg-white/[0.02] text-xs text-[#8B8B9E]">
            API Version <span className="text-[#F5F5F7] font-mono">v1.2.0</span>
          </div>
        </div>
      </aside>

      {/* ---- Content ---- */}
      <main ref={contentRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 lg:px-12 py-16">
          {/* ============================================================ */}
          {/*  QUICKSTART                                                   */}
          {/* ============================================================ */}
          <section id="quickstart" className="mb-20">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div className="flex items-center gap-2 mb-2">
                <Zap size={14} className="text-[#00D4FF]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-[#00D4FF]">
                  Getting started
                </span>
              </div>
              <h2 className="text-3xl font-bold mb-2">Quickstart</h2>
              <p className="text-[#8B8B9E] text-lg mb-8">
                Go from zero to your first loop detection in under 5 minutes.
              </p>

              <Step number={1} title="Create your account and get an API key">
                <p className="text-sm text-[#8B8B9E]">
                  Sign up at{" "}
                  <span className="text-[#00D4FF]">app.agentbreaker.dev</span>, create
                  a project, and copy your API key from the Settings page.
                </p>
              </Step>

              <Step number={2} title="Install the SDK">
                <CodeBlock code="$ pip install agentbreaker" language="bash" />
              </Step>

              <Step number={3} title="Add AgentBreaker to your agent">
                <CodeBlock
                  language="python"
                  title="main.py"
                  code={`from agentbreaker import AgentBreaker

ab = AgentBreaker(api_key="ab_live_xxxxxxxx")

# Inside your agent loop
for step in agent.run(task):
    verdict = ab.ingest(step)       # Send each step
    if verdict.should_kill:         # Circuit breaker triggered
        agent.stop(reason=verdict.reason)
        break`}
                />
              </Step>

              <Step number={4} title="See results in the dashboard">
                <p className="text-sm text-[#8B8B9E]">
                  Open the{" "}
                  <Link to="/overview" className="text-[#00D4FF] hover:underline">
                    Dashboard
                  </Link>{" "}
                  to see real-time detection across all 8 dimensions. Incidents appear
                  within seconds of detection.
                </p>
              </Step>
            </motion.div>
          </section>

          {/* ============================================================ */}
          {/*  INSTALLATION                                                 */}
          {/* ============================================================ */}
          <section id="installation" className="mb-20">
            <h2 className="text-2xl font-bold mb-4">Installation</h2>
            <p className="text-[#8B8B9E] mb-4">
              AgentBreaker requires <InlineCode>Python 3.9+</InlineCode> and can be
              installed via pip.
            </p>

            <CodeBlock
              language="bash"
              title="Install"
              code={`# Install the latest stable version
$ pip install agentbreaker

# Or install with optional async support
$ pip install agentbreaker[async]

# Verify installation
$ python -c "import agentbreaker; print(agentbreaker.__version__)"`}
            />

            <h3 className="text-lg font-semibold mt-6 mb-3">Requirements</h3>
            <DocTable
              headers={["Dependency", "Version", "Purpose"]}
              rows={[
                ["Python", ">=3.9", "Runtime"],
                ["httpx", ">=0.24", "HTTP client"],
                ["websockets", ">=11.0", "Real-time events"],
                ["pydantic", ">=2.0", "Data validation"],
              ]}
            />

            <Callout type="info">
              The SDK automatically detects your framework (LangChain, CrewAI,
              AutoGen) and instruments agent steps. No manual instrumentation
              required for supported frameworks.
            </Callout>
          </section>

          {/* ============================================================ */}
          {/*  CONFIGURATION                                                */}
          {/* ============================================================ */}
          <section id="configuration" className="mb-20">
            <h2 className="text-2xl font-bold mb-4">Configuration</h2>
            <p className="text-[#8B8B9E] mb-6">
              Configure AgentBreaker through the SDK constructor, environment
              variables, or a configuration file.
            </p>

            <h3 className="text-lg font-semibold mb-3">API Key</h3>
            <p className="text-sm text-[#8B8B9E] mb-3">
              Set your API key via environment variable (recommended) or pass it
              directly.
            </p>
            <CodeBlock
              language="bash"
              title=".env"
              code={`AGENTBREAKER_API_KEY=ab_live_xxxxxxxxxxxxxxxx
AGENTBREAKER_PROJECT_ID=proj_xxxxxxxx`}
            />

            <h3 className="text-lg font-semibold mt-8 mb-3">SDK Configuration</h3>
            <CodeBlock
              language="python"
              title="config.py"
              code={`from agentbreaker import AgentBreaker

ab = AgentBreaker(
    api_key="ab_live_xxxxxxxx",       # Or set AGENTBREAKER_API_KEY env var
    project_id="proj_xxxxxxxx",       # Optional, uses default project
    base_url="https://api.agentbreaker.dev",

    # Detection thresholds (0.0 - 1.0)
    thresholds={
        "semantic_similarity": 0.85,  # Cosine similarity cutoff
        "reasoning_loop": 0.70,       # SCC detection sensitivity
        "goal_drift": 0.60,           # Drift from original task
        "error_cascade": 0.80,        # Consecutive failure ratio
        "cost_velocity": 0.75,        # Cost growth rate trigger
        "token_entropy": 0.65,        # Entropy collapse threshold
        "context_inflation": 0.70,    # Context bloat percentage
        "diminishing_returns": 0.60,  # Novelty ratio minimum
    },

    # Circuit breaker settings
    auto_kill=True,                   # Automatically stop on incident
    kill_threshold=0.85,              # Composite score to trigger kill
    cooldown_seconds=30,              # Minimum time between kills
    max_steps=1000,                   # Hard limit on agent steps

    # Real-time
    enable_websocket=True,            # Enable live event streaming
    webhook_url=None,                 # Optional webhook for incidents
)`}
            />

            <h3 className="text-lg font-semibold mt-8 mb-3">Threshold Customization</h3>
            <p className="text-sm text-[#8B8B9E] mb-3">
              Each detection dimension has an independent threshold. Lower values
              increase sensitivity (more detections), higher values reduce false
              positives. You can adjust thresholds per-project in the{" "}
              <Link to="/settings" className="text-[#00D4FF] hover:underline">
                Settings
              </Link>{" "}
              page or via the SDK.
            </p>
            <Callout type="warning">
              Setting thresholds below 0.5 may generate excessive false positives.
              We recommend starting with defaults and tuning based on your
              incident history.
            </Callout>
          </section>

          {/* ============================================================ */}
          {/*  DETECTION DIMENSIONS                                         */}
          {/* ============================================================ */}
          <section id="detection-dimensions" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">Detection Dimensions</h2>
            <p className="text-[#8B8B9E] mb-6">
              AgentBreaker analyzes agent behavior across 8 independent dimensions.
              Each dimension contributes a weighted score to the composite risk
              assessment. Click any dimension to learn more.
            </p>

            <DimensionCard
              name="1. Semantic Similarity"
              description="Detects when an agent repeats semantically identical outputs across steps."
              howItWorks="Computes cosine similarity between consecutive step outputs using sentence-transformers (all-MiniLM-L6-v2). When similarity exceeds the threshold across a sliding window of steps, a semantic loop is flagged."
              threshold="85% cosine similarity over 3+ consecutive steps"
              weight="0.20 (highest) - Semantic loops are the most common failure mode."
              example="A coding agent asked to fix a bug keeps generating the same patch, reverting it, then re-applying it. Each output is nearly identical (92% cosine similarity) despite appearing as 'new' attempts."
            />

            <DimensionCard
              name="2. Reasoning Loop"
              description="Identifies circular reasoning patterns where the agent revisits previous conclusions."
              howItWorks="Models the agent's reasoning chain as a directed graph. Applies Tarjan's Strongly Connected Components (SCC) algorithm to detect cycles. An SCC of size >= 2 indicates circular reasoning."
              threshold="SCC detection with cycle length >= 2 nodes"
              weight="0.18 - Circular reasoning often precedes semantic loops."
              example="A research agent concludes 'X depends on Y', then later concludes 'Y depends on X', creating a logical cycle that prevents progress on either conclusion."
            />

            <DimensionCard
              name="3. Goal Drift"
              description="Measures how far the agent's current activity has drifted from its original task."
              howItWorks="Anchors the original task description as a semantic vector. At each step, computes the cosine distance between the current step's semantic vector and the anchor. Drift is normalized over the step count."
              threshold="60% drift from original task vector"
              weight="0.14 - Goal drift wastes resources on irrelevant subtasks."
              example="An agent tasked with 'summarize this PDF' starts browsing the web for related papers, then begins comparing academic citation formats, completely abandoning the original summarization task."
            />

            <DimensionCard
              name="4. Error Cascade"
              description="Detects chains of consecutive failures indicating the agent cannot recover."
              howItWorks="Tracks consecutive steps that result in errors, exceptions, or explicit failure signals. A cascade is detected when the failure ratio over a sliding window exceeds the threshold."
              threshold="80% failure rate over a 5-step window"
              weight="0.12 - Cascading errors burn tokens without progress."
              example="An agent attempting API calls receives 401 errors repeatedly, tries different authentication methods that all fail, generating 15 consecutive error steps before being stopped."
            />

            <DimensionCard
              name="5. Cost Velocity"
              description="Monitors for exponential growth in token consumption or API costs."
              howItWorks="Fits an exponential curve to the cumulative cost data over time. If the growth rate coefficient exceeds the threshold, indicating super-linear cost acceleration, an alert is triggered."
              threshold="Cost growth rate coefficient > 0.75"
              weight="0.12 - Protects against runaway costs."
              example="An agent processing data starts spawning sub-agents, each of which spawns more sub-agents. Token consumption grows from 1K to 4K to 16K to 64K tokens per step in a recursive explosion."
            />

            <DimensionCard
              name="6. Token Entropy"
              description="Detects when agent outputs become repetitive or degenerate at the token level."
              howItWorks="Computes Shannon entropy of the token distribution in agent outputs, combined with LZ77 compression ratio analysis. Low entropy or high compressibility indicates degenerate text (repeated phrases, filler content)."
              threshold="Entropy below 65% of baseline or compression ratio > 0.7"
              weight="0.08 - Catches degenerate outputs that semantic similarity may miss."
              example="An agent starts outputting 'I understand. Let me try again. I understand. Let me try again.' in a loop, producing text with very low token entropy despite slightly varying surrounding context."
            />

            <DimensionCard
              name="7. Context Inflation"
              description="Monitors for unbounded growth of the context window."
              howItWorks="Tracks the context window utilization percentage over time. Flags when the context grows faster than a linear projection based on task complexity, indicating the agent is accumulating unnecessary context."
              threshold="Context usage growing 70% faster than projected"
              weight="0.08 - Context bloat leads to degraded reasoning and higher costs."
              example="A data analysis agent keeps appending full query results to its context instead of summarizing them, growing from 2K to 120K tokens in 20 steps while the actual analysis requires only a few data points."
            />

            <DimensionCard
              name="8. Diminishing Returns"
              description="Tracks whether the agent is still producing novel, useful output."
              howItWorks="Computes a 'novelty ratio' by comparing each new step's output against all previous outputs using MinHash signatures. The ratio of genuinely new information to total output is tracked over time."
              threshold="Novelty ratio below 60% over a 5-step window"
              weight="0.08 - Low novelty means the agent is wasting resources."
              example="A writing agent asked to brainstorm ideas generates 50 suggestions, but after the first 15, each new suggestion is a minor rephrasing of a previous one, with the novelty ratio dropping from 90% to 12%."
            />
          </section>

          {/* ============================================================ */}
          {/*  API REFERENCE                                                */}
          {/* ============================================================ */}
          <section id="api-reference" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">API Reference</h2>
            <p className="text-[#8B8B9E] mb-6">
              Base URL:{" "}
              <InlineCode>https://api.agentbreaker.dev/api/v1</InlineCode>
              <br />
              All requests require an{" "}
              <InlineCode>Authorization: Bearer ab_live_xxx</InlineCode> header.
            </p>

            <Endpoint
              method="POST"
              path="/api/v1/ingest/step"
              description="Submit an agent step for real-time analysis. Returns a verdict with risk scores across all 8 dimensions and a kill recommendation."
              requestBody={`{
  "agent_id": "agent_abc123",
  "step_number": 42,
  "input": "Fix the authentication bug in auth.py",
  "output": "I'll modify the login function to...",
  "tokens_used": 1250,
  "cost_usd": 0.0037,
  "error": null,
  "metadata": {
    "model": "gpt-4o",
    "framework": "langchain"
  }
}`}
              responseBody={`{
  "verdict_id": "vrd_x7k2m9",
  "should_kill": false,
  "composite_score": 0.34,
  "dimensions": {
    "semantic_similarity": 0.12,
    "reasoning_loop": 0.00,
    "goal_drift": 0.18,
    "error_cascade": 0.00,
    "cost_velocity": 0.45,
    "token_entropy": 0.82,
    "context_inflation": 0.21,
    "diminishing_returns": 0.34
  },
  "incident": null,
  "warnings": ["cost_velocity approaching threshold"]
}`}
            />

            <Endpoint
              method="GET"
              path="/api/v1/agents"
              description="List all agents in the current project with their latest status and step count."
              responseBody={`{
  "agents": [
    {
      "agent_id": "agent_abc123",
      "name": "CodeFixer",
      "status": "running",
      "total_steps": 142,
      "incidents": 2,
      "last_seen": "2026-03-20T14:32:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}`}
            />

            <Endpoint
              method="GET"
              path="/api/v1/incidents"
              description="List all incidents with filtering by type, severity, and time range. Supports pagination."
              responseBody={`{
  "incidents": [
    {
      "incident_id": "inc_9f3k2x",
      "agent_id": "agent_abc123",
      "type": "semantic_loop",
      "severity": "critical",
      "composite_score": 0.92,
      "step_range": [38, 45],
      "auto_killed": true,
      "created_at": "2026-03-20T14:28:00Z",
      "resolved_at": "2026-03-20T14:28:02Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}`}
            />

            <Endpoint
              method="GET"
              path="/api/v1/analytics/overview"
              description="Returns dashboard KPIs including total agents, incidents, cost savings, and detection accuracy for the current project."
              responseBody={`{
  "total_agents": 47,
  "active_agents": 12,
  "total_incidents": 234,
  "incidents_today": 8,
  "total_steps_analyzed": 158420,
  "estimated_cost_saved_usd": 4832.50,
  "detection_accuracy": 0.967,
  "avg_detection_latency_ms": 45,
  "top_incident_type": "semantic_loop",
  "period": "last_30_days"
}`}
            />
          </section>

          {/* ============================================================ */}
          {/*  SDK REFERENCE                                                */}
          {/* ============================================================ */}
          <section id="sdk-reference" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">SDK Reference</h2>
            <p className="text-[#8B8B9E] mb-6">
              The Python SDK provides a high-level interface for interacting with
              AgentBreaker. All methods are available in both sync and async variants.
            </p>

            <h3 className="text-lg font-semibold mb-3">
              <InlineCode>AgentBreaker</InlineCode> Class
            </h3>
            <CodeBlock
              language="python"
              title="Core Methods"
              code={`class AgentBreaker:
    def __init__(self, api_key: str, **kwargs) -> None:
        """Initialize the AgentBreaker client."""

    def ingest(self, step: AgentStep) -> Verdict:
        """Submit a step for analysis. Returns verdict with risk scores."""

    def kill(self, agent_id: str, reason: str) -> KillConfirmation:
        """Manually trigger a circuit break for an agent."""

    def get_agent(self, agent_id: str) -> AgentInfo:
        """Retrieve agent details and current status."""

    def list_incidents(
        self,
        agent_id: str = None,
        severity: str = None,
        limit: int = 20,
    ) -> list[Incident]:
        """List incidents with optional filtering."""

    def get_analytics(self, period: str = "30d") -> AnalyticsOverview:
        """Get dashboard KPIs for the current project."""

    def connect_websocket(
        self, on_event: Callable[[Event], None]
    ) -> WebSocketConnection:
        """Open a real-time WebSocket connection for live events."""

    def update_thresholds(self, thresholds: dict[str, float]) -> None:
        """Update detection thresholds for the current project."""`}
            />

            <h3 className="text-lg font-semibold mt-8 mb-3">Data Models</h3>
            <CodeBlock
              language="python"
              title="Models"
              code={`from dataclasses import dataclass

@dataclass
class AgentStep:
    agent_id: str
    step_number: int
    input: str
    output: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    metadata: dict = None

@dataclass
class Verdict:
    verdict_id: str
    should_kill: bool
    composite_score: float          # 0.0 - 1.0
    dimensions: dict[str, float]    # Score per dimension
    incident: Incident | None
    warnings: list[str]

@dataclass
class Incident:
    incident_id: str
    agent_id: str
    type: str                       # e.g. "semantic_loop"
    severity: str                   # "warning" | "critical"
    composite_score: float
    step_range: tuple[int, int]
    auto_killed: bool
    created_at: str`}
            />

            <h3 className="text-lg font-semibold mt-8 mb-3">Async Usage</h3>
            <CodeBlock
              language="python"
              title="async_example.py"
              code={`from agentbreaker import AsyncAgentBreaker

ab = AsyncAgentBreaker(api_key="ab_live_xxxxxxxx")

async def monitor_agent(agent):
    async for step in agent.run_async(task):
        verdict = await ab.ingest(step)
        if verdict.should_kill:
            await agent.stop(reason=verdict.reason)
            break`}
            />
          </section>

          {/* ============================================================ */}
          {/*  WEBSOCKET EVENTS                                             */}
          {/* ============================================================ */}
          <section id="websocket-events" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">WebSocket Events</h2>
            <p className="text-[#8B8B9E] mb-6">
              Connect to{" "}
              <InlineCode>wss://api.agentbreaker.dev/ws/live</InlineCode> for
              real-time event streaming. Authenticate by passing your API key as a
              query parameter or in the first message.
            </p>

            <CodeBlock
              language="python"
              title="WebSocket Connection"
              code={`import asyncio
from agentbreaker import AsyncAgentBreaker

ab = AsyncAgentBreaker(api_key="ab_live_xxxxxxxx")

async def listen():
    def on_event(event):
        match event.type:
            case "incident":
                print(f"INCIDENT: {event.data.type} on {event.data.agent_id}")
            case "warning":
                print(f"WARNING: {event.data.message}")
            case "step":
                print(f"Step {event.data.step_number} analyzed")

    ws = ab.connect_websocket(on_event=on_event)
    await ws.wait()

asyncio.run(listen())`}
            />

            <h3 className="text-lg font-semibold mt-8 mb-3">Event Types</h3>
            <DocTable
              headers={["Event Type", "Trigger", "Payload"]}
              rows={[
                [
                  "incident",
                  "A detection threshold was exceeded",
                  "{ type, agent_id, severity, composite_score, dimensions }",
                ],
                [
                  "warning",
                  "A dimension is approaching its threshold",
                  "{ dimension, current_score, threshold, agent_id }",
                ],
                [
                  "step",
                  "A step was successfully analyzed",
                  "{ agent_id, step_number, composite_score }",
                ],
                [
                  "kill",
                  "Circuit breaker was triggered",
                  "{ agent_id, reason, incident_id, auto }",
                ],
                [
                  "heartbeat",
                  "Every 30 seconds",
                  "{ timestamp, connected_agents }",
                ],
              ]}
            />
          </section>

          {/* ============================================================ */}
          {/*  INCIDENT TYPES                                               */}
          {/* ============================================================ */}
          <section id="incident-types" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">Incident Types</h2>
            <p className="text-[#8B8B9E] mb-6">
              Each incident maps to a specific detection dimension. Incidents are
              classified by severity:{" "}
              <span className="text-[#F59E0B]">warning</span> (approaching
              threshold) or <span className="text-[#EF4444]">critical</span>{" "}
              (threshold exceeded, kill recommended).
            </p>

            <DocTable
              headers={["Incident Type", "Dimension", "Severity Trigger", "Description"]}
              rows={[
                [
                  "semantic_loop",
                  "Semantic Similarity",
                  ">= 0.85 cosine",
                  "Agent outputs are semantically identical across steps",
                ],
                [
                  "reasoning_loop",
                  "Reasoning Loop",
                  "SCC >= 2 nodes",
                  "Circular reasoning detected in agent logic chain",
                ],
                [
                  "goal_drift",
                  "Goal Drift",
                  ">= 0.60 drift",
                  "Agent has wandered far from its original objective",
                ],
                [
                  "error_cascade",
                  "Error Cascade",
                  ">= 80% failure rate",
                  "Agent is in an unrecoverable error loop",
                ],
                [
                  "cost_spike",
                  "Cost Velocity",
                  "Exp. growth coeff > 0.75",
                  "Token or API costs are growing exponentially",
                ],
                [
                  "entropy_collapse",
                  "Token Entropy",
                  "Entropy < 65% baseline",
                  "Agent output has become degenerate or repetitive",
                ],
                [
                  "context_bloat",
                  "Context Inflation",
                  "> 70% inflation rate",
                  "Context window is growing unsustainably",
                ],
                [
                  "diminishing_returns",
                  "Diminishing Returns",
                  "Novelty < 60%",
                  "Agent is no longer producing useful new output",
                ],
              ]}
            />

            <Callout type="info">
              When multiple dimensions trigger simultaneously, AgentBreaker creates a
              single compound incident with the highest severity. The incident
              detail page shows the breakdown across all contributing dimensions.
            </Callout>
          </section>

          {/* ============================================================ */}
          {/*  RATE LIMITS & PRICING                                        */}
          {/* ============================================================ */}
          <section id="rate-limits-pricing" className="mb-20">
            <h2 className="text-2xl font-bold mb-2">Rate Limits & Pricing</h2>

            <h3 className="text-lg font-semibold mt-6 mb-3">Rate Limits</h3>
            <DocTable
              headers={["Tier", "Requests / minute", "Agents", "WebSocket connections"]}
              rows={[
                ["Free", "100", "5", "1"],
                ["Pro", "1,000", "50", "5"],
                ["Team", "5,000", "200", "20"],
                ["Enterprise", "Unlimited", "Unlimited", "Unlimited"],
              ]}
            />
            <p className="text-sm text-[#8B8B9E] mb-8">
              Rate limit headers are included in every response:{" "}
              <InlineCode>X-RateLimit-Remaining</InlineCode>,{" "}
              <InlineCode>X-RateLimit-Reset</InlineCode>. When exceeded, the API
              returns <InlineCode>429 Too Many Requests</InlineCode> with a{" "}
              <InlineCode>Retry-After</InlineCode> header.
            </p>

            <h3 className="text-lg font-semibold mb-4">Pricing</h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <PricingCard
                name="Free"
                price="$0 / mo"
                features={[
                  "100 requests / minute",
                  "5 agents",
                  "7-day data retention",
                  "All 8 detection dimensions",
                  "Community support",
                ]}
              />
              <PricingCard
                name="Pro"
                price="$49 / mo"
                highlighted
                features={[
                  "1,000 requests / minute",
                  "50 agents",
                  "90-day data retention",
                  "Custom thresholds",
                  "Webhook integrations",
                  "Priority support",
                ]}
              />
              <PricingCard
                name="Team"
                price="$199 / mo"
                features={[
                  "5,000 requests / minute",
                  "200 agents",
                  "1-year data retention",
                  "SSO / SAML",
                  "Audit logs",
                  "Dedicated support",
                ]}
              />
              <PricingCard
                name="Enterprise"
                price="Custom"
                features={[
                  "Unlimited everything",
                  "On-premise deployment",
                  "Custom SLAs",
                  "SOC 2 compliance",
                  "Dedicated CSM",
                  "24/7 phone support",
                ]}
              />
            </div>
          </section>

          {/* Footer */}
          <div className="border-t border-white/[0.06] pt-8 pb-12 text-center">
            <p className="text-sm text-[#8B8B9E]">
              Need help?{" "}
              <span className="text-[#00D4FF]">support@agentbreaker.dev</span>
              {" "}&middot;{" "}
              <span className="text-[#8B8B9E]">API Status: </span>
              <span className="text-[#10B981]">Operational</span>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
