import { useState } from "react";
import { motion } from "framer-motion";
import { Calculator, TrendingDown, Leaf, DollarSign, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

/* ------------------------------------------------------------------ */
/*  ROI Calculator — proves value to enterprise buyers                 */
/* ------------------------------------------------------------------ */

interface ROIInputs {
  agentCount: number;
  avgCostPerAgent: number;
  runsPerDay: number;
  failureRate: number;
  avgWastedSteps: number;
  costPerStep: number;
}

function calculateROI(inputs: ROIInputs) {
  const {
    agentCount,
    avgCostPerAgent,
    runsPerDay,
    failureRate,
    avgWastedSteps,
    costPerStep,
  } = inputs;

  // Monthly calculations
  const runsPerMonth = runsPerDay * 30;
  const totalRunsPerMonth = agentCount * runsPerMonth;
  const failedRunsPerMonth = totalRunsPerMonth * (failureRate / 100);
  const wastedCostPerMonth = failedRunsPerMonth * avgWastedSteps * costPerStep;

  // AgentBreaker catches ~85% of failures on average (conservative)
  const detectionRate = 0.85;
  // Average early detection saves 70% of wasted steps
  const earlyDetectionSaving = 0.70;

  const monthlySavings = wastedCostPerMonth * detectionRate * earlyDetectionSaving;
  const annualSavings = monthlySavings * 12;

  // Carbon calculations (based on real methodology from carbon.py)
  const kwhPerStep = 0.002; // medium model class
  const co2PerKwh = 0.39; // us-east
  const wastedStepsAvoidedPerMonth = failedRunsPerMonth * detectionRate * avgWastedSteps * earlyDetectionSaving;
  const kwhSaved = wastedStepsAvoidedPerMonth * kwhPerStep;
  const co2SavedKg = (kwhSaved * co2PerKwh) / 1000;
  const annualCO2SavedKg = co2SavedKg * 12;

  // Plan recommendation
  let plan = "Starter";
  let planCost = 199;
  if (agentCount > 500) {
    plan = "Enterprise";
    planCost = 4999;
  } else if (agentCount > 50) {
    plan = "Growth";
    planCost = 999;
  }

  const roi = ((annualSavings - planCost * 12) / (planCost * 12)) * 100;

  return {
    monthlySavings,
    annualSavings,
    failedRunsPerMonth: Math.round(failedRunsPerMonth),
    wastedCostPerMonth,
    plan,
    planCost,
    roi: Math.max(0, roi),
    annualCO2SavedKg,
    paybackDays: planCost > 0 ? Math.max(1, Math.round((planCost / monthlySavings) * 30)) : 0,
  };
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export default function ROICalculator() {
  const [inputs, setInputs] = useState<ROIInputs>({
    agentCount: 100,
    avgCostPerAgent: 2.5,
    runsPerDay: 50,
    failureRate: 8,
    avgWastedSteps: 45,
    costPerStep: 0.03,
  });

  const results = calculateROI(inputs);

  const sliders: {
    key: keyof ROIInputs;
    label: string;
    min: number;
    max: number;
    step: number;
    unit: string;
    tooltip: string;
  }[] = [
    { key: "agentCount", label: "Active agents", min: 5, max: 5000, step: 5, unit: "", tooltip: "Total concurrent agents in production" },
    { key: "runsPerDay", label: "Agent runs per day", min: 1, max: 500, step: 1, unit: "/day", tooltip: "Average executions per agent per day" },
    { key: "failureRate", label: "Failure rate", min: 1, max: 30, step: 0.5, unit: "%", tooltip: "% of runs that enter a failure mode (loops, errors, drift)" },
    { key: "avgWastedSteps", label: "Avg wasted steps per failure", min: 5, max: 200, step: 5, unit: " steps", tooltip: "Steps wasted before manual detection" },
    { key: "costPerStep", label: "Cost per step", min: 0.001, max: 0.20, step: 0.001, unit: "", tooltip: "Average LLM API cost per agent step" },
  ];

  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* Header */}
      <nav className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/landing" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
              <Calculator className="w-4 h-4 text-accent" />
            </div>
            <span className="font-bold text-text-primary text-lg tracking-tight">
              ROI Calculator
            </span>
          </Link>
          <Link
            to="/login"
            className="px-4 py-2 bg-accent text-background text-sm font-semibold rounded-lg hover:brightness-110 transition-all"
          >
            Start Free Trial
          </Link>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold">
            How much are runaway agents costing you?
          </h1>
          <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
            Adjust the sliders to match your deployment. See exactly how much AgentBreaker saves.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-12">
          {/* Inputs */}
          <div className="space-y-8">
            {sliders.map((s) => (
              <div key={s.key}>
                <div className="flex items-baseline justify-between mb-2">
                  <label className="text-sm font-medium text-text-primary">
                    {s.label}
                  </label>
                  <span className="text-lg font-mono font-bold text-accent">
                    {s.key === "costPerStep" ? `$${inputs[s.key].toFixed(3)}` : `${inputs[s.key].toLocaleString()}${s.unit}`}
                  </span>
                </div>
                <input
                  type="range"
                  min={s.min}
                  max={s.max}
                  step={s.step}
                  value={inputs[s.key]}
                  onChange={(e) =>
                    setInputs((prev) => ({
                      ...prev,
                      [s.key]: parseFloat(e.target.value),
                    }))
                  }
                  className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-accent"
                />
                <div className="flex justify-between text-xs text-text-muted mt-1">
                  <span>{s.key === "costPerStep" ? `$${s.min}` : s.min}</span>
                  <span>{s.key === "costPerStep" ? `$${s.max}` : `${s.max.toLocaleString()}`}</span>
                </div>
                <p className="text-xs text-text-muted mt-1">{s.tooltip}</p>
              </div>
            ))}
          </div>

          {/* Results */}
          <div className="space-y-6">
            {/* Annual savings hero */}
            <motion.div
              key={results.annualSavings}
              initial={{ scale: 0.95, opacity: 0.5 }}
              animate={{ scale: 1, opacity: 1 }}
              className="rounded-2xl border border-accent/30 bg-accent/[0.04] p-8 text-center"
            >
              <p className="text-sm font-medium text-accent uppercase tracking-wider">
                Estimated Annual Savings
              </p>
              <p className="mt-2 text-5xl md:text-6xl font-bold font-mono text-text-primary">
                {formatCurrency(results.annualSavings)}
              </p>
              <p className="mt-2 text-text-muted">
                {formatCurrency(results.monthlySavings)} per month
              </p>
            </motion.div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-border bg-surface/40 p-5">
                <DollarSign className="w-5 h-5 text-success mb-2" />
                <p className="text-2xl font-bold font-mono">{results.roi.toFixed(0)}%</p>
                <p className="text-xs text-text-muted mt-1">Return on investment</p>
              </div>
              <div className="rounded-xl border border-border bg-surface/40 p-5">
                <TrendingDown className="w-5 h-5 text-warning mb-2" />
                <p className="text-2xl font-bold font-mono">{results.paybackDays} days</p>
                <p className="text-xs text-text-muted mt-1">Payback period</p>
              </div>
              <div className="rounded-xl border border-border bg-surface/40 p-5">
                <Leaf className="w-5 h-5 text-success mb-2" />
                <p className="text-2xl font-bold font-mono">{results.annualCO2SavedKg.toFixed(0)} kg</p>
                <p className="text-xs text-text-muted mt-1">CO2 avoided per year</p>
              </div>
              <div className="rounded-xl border border-border bg-surface/40 p-5">
                <Calculator className="w-5 h-5 text-accent mb-2" />
                <p className="text-2xl font-bold font-mono">{results.failedRunsPerMonth.toLocaleString()}</p>
                <p className="text-xs text-text-muted mt-1">Failed runs caught / month</p>
              </div>
            </div>

            {/* Plan recommendation */}
            <div className="rounded-xl border border-border bg-surface/40 p-6">
              <p className="text-sm text-text-muted">Recommended plan</p>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-xl font-bold text-text-primary">
                  {results.plan}
                </span>
                <span className="text-lg font-mono text-accent">
                  {results.planCost} EUR/mo
                </span>
              </div>
              <p className="mt-3 text-sm text-text-muted">
                Your savings of {formatCurrency(results.monthlySavings)}/mo are{" "}
                <span className="text-success font-semibold">
                  {(results.monthlySavings / results.planCost).toFixed(0)}x
                </span>{" "}
                the cost of the plan.
              </p>
              <Link
                to="/login"
                className="mt-4 w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-accent text-background font-semibold rounded-lg hover:brightness-110 transition-all"
              >
                Start Free Trial
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            {/* Methodology note */}
            <p className="text-xs text-text-muted leading-relaxed">
              Calculations assume 85% detection rate and 70% early-detection savings based on
              production benchmarks. Actual results depend on agent architecture, LLM provider,
              and failure mode distribution. CO2 calculations use IEA 2024 US-East emission
              factors (0.39 kg CO2/kWh) and medium model class inference estimates.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
