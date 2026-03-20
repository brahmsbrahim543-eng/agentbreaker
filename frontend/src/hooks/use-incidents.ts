import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";

export type IncidentType =
  | "semantic_loop"
  | "error_cascade"
  | "cost_spike"
  | "diminishing_returns"
  | "context_bloat";

export interface Incident {
  id: string;
  agent_id: string;
  agent_name: string;
  incident_type: IncidentType;
  risk_score_at_kill: number;
  steps_before_kill: number;
  kill_reason_detail: string;
  cost_avoided: number;
  co2_avoided: number;
  total_cost_at_kill: number;
  created_at: string;
  snapshot_steps: SnapshotStep[];
}

export interface SnapshotStep {
  step_number: number;
  input: string;
  output: string;
  tool: string | null;
  risk_score: number;
  is_duplicate: boolean;
}

interface IncidentsResponse {
  items: Incident[];
  total: number;
}

const h = (hours: number) => new Date(Date.now() - hours * 3600000).toISOString();

const MOCK_INCIDENTS: Incident[] = [
  {
    id: "inc-001", agent_id: "2", agent_name: "pricing-optimizer", incident_type: "semantic_loop",
    risk_score_at_kill: 92, steps_before_kill: 234, kill_reason_detail: "Agent entered a semantic loop: the last 5 outputs were functionally identical, each repeating the same pricing recommendation with minor wording variations. The agent was consuming tokens without producing new value. Risk score exceeded threshold at 92/100.",
    cost_avoided: 34.20, co2_avoided: 8.7, total_cost_at_kill: 45.67, created_at: h(2),
    snapshot_steps: [
      { step_number: 234, input: "Recalculate optimal price for SKU-8821", output: "Based on market analysis, the optimal price for SKU-8821 is 24,99 €. This represents a 12% margin improvement.", tool: "pricing_engine", risk_score: 92, is_duplicate: true },
      { step_number: 233, input: "Recalculate optimal price for SKU-8821", output: "After analyzing current market conditions, I recommend setting SKU-8821 at 24,99 € for optimal margin performance (+12%).", tool: "pricing_engine", risk_score: 89, is_duplicate: true },
      { step_number: 232, input: "Recalculate optimal price for SKU-8821", output: "The recommended price for SKU-8821 is 24,99 €, yielding a 12% margin improvement based on competitive analysis.", tool: "pricing_engine", risk_score: 85, is_duplicate: true },
      { step_number: 231, input: "Recalculate optimal price for SKU-8821", output: "Market data suggests pricing SKU-8821 at 24,99 € for a 12% margin gain. This aligns with competitor positioning.", tool: "pricing_engine", risk_score: 78, is_duplicate: true },
      { step_number: 230, input: "Recalculate optimal price for SKU-8821", output: "Optimal pricing for SKU-8821: 24,99 €. Expected margin improvement: 12% over current pricing.", tool: "pricing_engine", risk_score: 71, is_duplicate: true },
      { step_number: 229, input: "Analyze competitor pricing for electronics category", output: "Competitor analysis complete. Average price point: 27,50 €. Our current price: 28,99 €. Recommendation: reduce to 24,99 €.", tool: "competitor_scraper", risk_score: 45, is_duplicate: false },
      { step_number: 228, input: "Pull latest sales data for SKU-8821", output: "SKU-8821 sales data: 142 units last 30 days, avg price 28,99 €, return rate 2.1%.", tool: "sales_db", risk_score: 38, is_duplicate: false },
    ],
  },
  {
    id: "inc-002", agent_id: "6", agent_name: "fraud-detection-agent", incident_type: "error_cascade",
    risk_score_at_kill: 88, steps_before_kill: 167, kill_reason_detail: "Agent triggered a cascading series of API errors when the external fraud database returned 503 errors. Instead of backing off, the agent retried aggressively, generating 45 failed requests in 30 seconds. Each retry attempt incurred token costs for prompt construction without successful execution.",
    cost_avoided: 22.80, co2_avoided: 5.4, total_cost_at_kill: 34.56, created_at: h(6),
    snapshot_steps: [
      { step_number: 167, input: "Retry fraud check for transaction TX-99412", output: "ERROR: External fraud API returned 503 Service Unavailable. Retrying...", tool: "fraud_api", risk_score: 88, is_duplicate: true },
      { step_number: 166, input: "Retry fraud check for transaction TX-99412", output: "ERROR: External fraud API returned 503 Service Unavailable. Attempting retry #44...", tool: "fraud_api", risk_score: 86, is_duplicate: true },
      { step_number: 165, input: "Retry fraud check for transaction TX-99412", output: "ERROR: External fraud API returned 503 Service Unavailable. Attempting retry #43...", tool: "fraud_api", risk_score: 84, is_duplicate: true },
      { step_number: 164, input: "Check fraud status for transaction TX-99412", output: "ERROR: Connection timeout to fraud detection service. Will retry.", tool: "fraud_api", risk_score: 79, is_duplicate: true },
      { step_number: 163, input: "Verify transaction TX-99412 against known patterns", output: "Transaction TX-99412 flagged for review. Amount: 2 340 €. Attempting external verification.", tool: "pattern_matcher", risk_score: 52, is_duplicate: false },
      { step_number: 162, input: "Process incoming transaction batch #445", output: "Batch #445 received: 23 transactions totaling 45 200 €. Starting fraud screening.", tool: null, risk_score: 35, is_duplicate: false },
    ],
  },
  {
    id: "inc-003", agent_id: "11", agent_name: "document-parser-v4", incident_type: "cost_spike",
    risk_score_at_kill: 95, steps_before_kill: 78, kill_reason_detail: "Agent's per-step cost spiked 40x above baseline when it began processing an unexpectedly large document (2,400 pages) by sending the entire content in each API call rather than chunking. Token usage jumped from ~500 tokens/step to ~20,000 tokens/step.",
    cost_avoided: 156.40, co2_avoided: 42.1, total_cost_at_kill: 89.45, created_at: h(12),
    snapshot_steps: [
      { step_number: 78, input: "Continue parsing page 78 of document LEGAL-2024-Q4.pdf", output: "Parsing page 78... [20,341 tokens consumed]. Extracted 3 clauses related to indemnification.", tool: "pdf_parser", risk_score: 95, is_duplicate: false },
      { step_number: 77, input: "Parse page 77 of document LEGAL-2024-Q4.pdf", output: "Parsing page 77... [19,876 tokens consumed]. Found 2 references to liability limitations.", tool: "pdf_parser", risk_score: 93, is_duplicate: false },
      { step_number: 76, input: "Parse page 76 of document LEGAL-2024-Q4.pdf", output: "Parsing page 76... [20,102 tokens consumed]. Extracted arbitration clause details.", tool: "pdf_parser", risk_score: 90, is_duplicate: false },
      { step_number: 75, input: "Parse page 75 of document LEGAL-2024-Q4.pdf", output: "Parsing page 75... [19,445 tokens consumed]. Processing force majeure section.", tool: "pdf_parser", risk_score: 86, is_duplicate: false },
      { step_number: 2, input: "Begin parsing document LEGAL-2024-Q4.pdf", output: "Document loaded: 2,400 pages, estimated 4.2M tokens. Starting sequential page processing.", tool: "pdf_parser", risk_score: 12, is_duplicate: false },
      { step_number: 1, input: "Process uploaded document for contract review", output: "Received document LEGAL-2024-Q4.pdf. Initializing parser.", tool: null, risk_score: 5, is_duplicate: false },
    ],
  },
  {
    id: "inc-004", agent_id: "16", agent_name: "onboarding-assistant", incident_type: "semantic_loop",
    risk_score_at_kill: 81, steps_before_kill: 201, kill_reason_detail: "Agent became stuck in a greeting loop, repeatedly asking the user for their name despite having already received and acknowledged it. The agent's context window was likely corrupted, causing it to lose track of conversation state.",
    cost_avoided: 18.90, co2_avoided: 4.2, total_cost_at_kill: 52.34, created_at: h(4),
    snapshot_steps: [
      { step_number: 201, input: "User said: I already told you, it's Sarah!", output: "I apologize for the confusion! Welcome to our platform. Could you please tell me your name so I can personalize your experience?", tool: null, risk_score: 81, is_duplicate: true },
      { step_number: 200, input: "User said: My name is Sarah, I said this 5 times", output: "Welcome! I'd love to help you get started. First, may I ask your name?", tool: null, risk_score: 78, is_duplicate: true },
      { step_number: 199, input: "User said: SARAH", output: "Thank you! To begin your onboarding journey, could you share your name with me?", tool: null, risk_score: 74, is_duplicate: true },
      { step_number: 198, input: "User said: It's Sarah", output: "Great to have you here! What's your name so I can set up your profile?", tool: null, risk_score: 68, is_duplicate: true },
      { step_number: 197, input: "User said: My name is Sarah", output: "Nice to meet you, Sarah! Let me set up your profile. What's your preferred name?", tool: "profile_api", risk_score: 42, is_duplicate: false },
    ],
  },
  {
    id: "inc-005", agent_id: "4", agent_name: "email-drafter", incident_type: "diminishing_returns",
    risk_score_at_kill: 67, steps_before_kill: 456, kill_reason_detail: "Agent spent 89 consecutive steps refining a single email draft, making increasingly minor edits (changing single words, adjusting punctuation) without meaningful improvement. Output quality plateaued at step 380 but the agent continued iterating.",
    cost_avoided: 8.45, co2_avoided: 2.1, total_cost_at_kill: 23.45, created_at: h(8),
    snapshot_steps: [
      { step_number: 456, input: "Refine the opening sentence one more time", output: "Changed 'Dear' to 'Hi' in the greeting. The email now reads: 'Hi Mr. Thompson, I hope this message finds you well...'", tool: "text_editor", risk_score: 67, is_duplicate: false },
      { step_number: 455, input: "Adjust the closing paragraph tone", output: "Modified closing from 'Best regards' to 'Kind regards'. No other changes.", tool: "text_editor", risk_score: 65, is_duplicate: false },
      { step_number: 454, input: "Check if the tone is professional enough", output: "Tone analysis: Professional (98.2%). Suggestion: consider changing one comma to a semicolon in paragraph 2.", tool: "tone_analyzer", risk_score: 63, is_duplicate: false },
      { step_number: 453, input: "Make the email more concise", output: "Removed one instance of 'very' from paragraph 3. Word count reduced from 187 to 186.", tool: "text_editor", risk_score: 61, is_duplicate: false },
      { step_number: 380, input: "Draft a follow-up email to Mr. Thompson", output: "Draft complete. Professional tone, 190 words, covers all 4 discussion points from the meeting. Ready for review.", tool: "text_editor", risk_score: 34, is_duplicate: false },
    ],
  },
  {
    id: "inc-006", agent_id: "9", agent_name: "meeting-summarizer", incident_type: "context_bloat",
    risk_score_at_kill: 71, steps_before_kill: 312, kill_reason_detail: "Agent's context window grew to 98% capacity as it accumulated full meeting transcripts without summarization. Instead of processing incrementally, it kept appending raw transcript data. Token usage per step increased exponentially.",
    cost_avoided: 14.30, co2_avoided: 3.8, total_cost_at_kill: 19.23, created_at: h(1),
    snapshot_steps: [
      { step_number: 312, input: "Add the latest 30-minute segment to context", output: "Context window at 98% capacity. Appending transcript segment 12 (4,200 tokens). Warning: approaching maximum context length.", tool: null, risk_score: 71, is_duplicate: false },
      { step_number: 311, input: "Continue transcription processing", output: "Transcript segment 11 appended (3,900 tokens). Total context: 96% utilized. 8,200 tokens remaining.", tool: "transcript_api", risk_score: 68, is_duplicate: false },
      { step_number: 310, input: "Process next transcript chunk", output: "Added segment 10 to running context. Context utilization: 92%. No summarization performed yet.", tool: "transcript_api", risk_score: 64, is_duplicate: false },
      { step_number: 309, input: "Load next meeting segment", output: "Segment 9 loaded (4,100 tokens). Running total context: 87%. Still accumulating before final summary.", tool: "transcript_api", risk_score: 59, is_duplicate: false },
      { step_number: 300, input: "Begin processing 3-hour board meeting recording", output: "Meeting recording loaded. Duration: 3h 12m. Estimated 15 segments. Beginning sequential processing.", tool: "transcript_api", risk_score: 22, is_duplicate: false },
    ],
  },
  {
    id: "inc-007", agent_id: "10", agent_name: "lead-qualifier", incident_type: "cost_spike",
    risk_score_at_kill: 76, steps_before_kill: 892, kill_reason_detail: "Agent began enriching leads with premium API calls (0,10 €/call) instead of standard lookups (0,001 €/call) after a configuration drift. 340 premium calls were made before detection.",
    cost_avoided: 28.60, co2_avoided: 6.2, total_cost_at_kill: 41.12, created_at: h(18),
    snapshot_steps: [
      { step_number: 892, input: "Enrich lead #4521 with full company profile", output: "Premium enrichment complete. Company: TechCorp Inc. Revenue: 45M €. Employees: 230. Cost: 0,10 €", tool: "enrichment_premium", risk_score: 76, is_duplicate: false },
      { step_number: 891, input: "Enrich lead #4520 with full company profile", output: "Premium enrichment complete. Company: DataFlow LLC. Revenue: 12M €. Employees: 45. Cost: 0,10 €", tool: "enrichment_premium", risk_score: 74, is_duplicate: false },
      { step_number: 890, input: "Enrich lead #4519 with company data", output: "Premium enrichment complete. Company: CloudBase. Revenue: 89M €. Employees: 560. Cost: 0,10 €", tool: "enrichment_premium", risk_score: 72, is_duplicate: false },
      { step_number: 550, input: "Qualify lead #3200", output: "Lead qualified via standard lookup. Score: 72/100. Industry: SaaS. Cost: 0,001 €", tool: "enrichment_standard", risk_score: 28, is_duplicate: false },
    ],
  },
  {
    id: "inc-008", agent_id: "14", agent_name: "report-generator", incident_type: "semantic_loop",
    risk_score_at_kill: 58, steps_before_kill: 423, kill_reason_detail: "Agent entered a loop regenerating the same executive summary section, producing nearly identical text each iteration. The loop was triggered by conflicting formatting instructions in the prompt template.",
    cost_avoided: 11.20, co2_avoided: 2.9, total_cost_at_kill: 28.90, created_at: h(24),
    snapshot_steps: [
      { step_number: 423, input: "Regenerate executive summary with bullet points", output: "Executive Summary: Q4 revenue grew 15% YoY to 12,4M €. Key drivers: (1) Enterprise expansion, (2) New product launches, (3) Reduced churn.", tool: "doc_generator", risk_score: 58, is_duplicate: true },
      { step_number: 422, input: "Reformat executive summary as numbered list", output: "Executive Summary: 1. Q4 revenue increased 15% year-over-year, reaching 12,4M €. 2. Growth driven by enterprise expansion. 3. New product launches contributed significantly.", tool: "doc_generator", risk_score: 55, is_duplicate: true },
      { step_number: 421, input: "Rewrite executive summary with more detail", output: "Executive Summary: Revenue for Q4 reached 12,4M €, a 15% improvement over the same period last year. Key growth drivers included enterprise account expansion, new product introductions, and improved customer retention.", tool: "doc_generator", risk_score: 51, is_duplicate: true },
      { step_number: 418, input: "Generate Q4 financial report", output: "Report structure: 1. Executive Summary, 2. Revenue Breakdown, 3. Cost Analysis, 4. Forecasts. Beginning generation...", tool: "doc_generator", risk_score: 30, is_duplicate: false },
    ],
  },
  {
    id: "inc-009", agent_id: "19", agent_name: "ab-test-evaluator", incident_type: "error_cascade",
    risk_score_at_kill: 63, steps_before_kill: 345, kill_reason_detail: "Statistical analysis service returned malformed JSON, causing the agent to repeatedly attempt parsing and re-requesting. 67 failed parse attempts logged before kill.",
    cost_avoided: 7.80, co2_avoided: 1.9, total_cost_at_kill: 18.90, created_at: h(36),
    snapshot_steps: [
      { step_number: 345, input: "Parse A/B test results from analytics API", output: "ERROR: JSON parse error at position 234. Unexpected token '<'. Retrying request...", tool: "analytics_api", risk_score: 63, is_duplicate: true },
      { step_number: 344, input: "Retry analytics data fetch", output: "ERROR: JSON parse error at position 234. Response appears to be HTML error page. Retrying...", tool: "analytics_api", risk_score: 61, is_duplicate: true },
      { step_number: 343, input: "Fetch A/B test metrics", output: "ERROR: Failed to parse response. Expected JSON but received HTML. Attempt 65 of unlimited.", tool: "analytics_api", risk_score: 58, is_duplicate: true },
      { step_number: 280, input: "Evaluate A/B test 'checkout-redesign-v2'", output: "Loading test data for 'checkout-redesign-v2'. Control: 12,400 users. Variant: 12,350 users.", tool: "analytics_api", risk_score: 22, is_duplicate: false },
    ],
  },
  {
    id: "inc-010", agent_id: "5", agent_name: "data-pipeline-orchestrator", incident_type: "cost_spike",
    risk_score_at_kill: 79, steps_before_kill: 3421, kill_reason_detail: "Pipeline agent triggered parallel processing of 200 data shards simultaneously instead of the configured batch size of 10. This caused a 20x spike in concurrent API calls and associated costs.",
    cost_avoided: 89.50, co2_avoided: 23.4, total_cost_at_kill: 156.78, created_at: h(0.5),
    snapshot_steps: [
      { step_number: 3421, input: "Process remaining data shards", output: "Spawned 200 parallel processing tasks. Estimated cost: 0,45 €/shard. Total batch cost projection: 90,00 €", tool: "batch_processor", risk_score: 79, is_duplicate: false },
      { step_number: 3420, input: "Check remaining unprocessed shards", output: "200 shards remaining. Attempting to process all in parallel for faster completion.", tool: null, risk_score: 72, is_duplicate: false },
      { step_number: 3419, input: "Continue data pipeline execution", output: "Batch 342 complete. 10 shards processed. Cost: 4,50 €. Moving to next batch.", tool: "batch_processor", risk_score: 35, is_duplicate: false },
    ],
  },
  {
    id: "inc-011", agent_id: "8", agent_name: "code-reviewer-bot", incident_type: "diminishing_returns",
    risk_score_at_kill: 54, steps_before_kill: 1567, kill_reason_detail: "Agent performed 120 successive linting passes on the same file, finding and fixing increasingly trivial issues (whitespace, import ordering) with no functional impact.",
    cost_avoided: 5.60, co2_avoided: 1.4, total_cost_at_kill: 67.89, created_at: h(48),
    snapshot_steps: [
      { step_number: 1567, input: "Run final linting pass on utils.ts", output: "Found 1 issue: trailing whitespace on line 234. Fixed. Running pass 121...", tool: "linter", risk_score: 54, is_duplicate: false },
      { step_number: 1566, input: "Check for remaining style issues", output: "Found 1 issue: import 'fs' should come before 'path' alphabetically. Fixed.", tool: "linter", risk_score: 52, is_duplicate: false },
      { step_number: 1450, input: "Review pull request #445", output: "PR #445 review complete. 3 critical issues found and documented. 2 suggestions made. Ready for developer review.", tool: "github_api", risk_score: 18, is_duplicate: false },
    ],
  },
  {
    id: "inc-012", agent_id: "15", agent_name: "sentiment-analyzer", incident_type: "semantic_loop",
    risk_score_at_kill: 83, steps_before_kill: 1089, kill_reason_detail: "Agent repeatedly re-analyzed the same batch of 50 customer reviews, producing identical sentiment scores each time. A missing 'processed' flag caused the batch to be re-queued indefinitely.",
    cost_avoided: 12.30, co2_avoided: 3.1, total_cost_at_kill: 14.56, created_at: h(3),
    snapshot_steps: [
      { step_number: 1089, input: "Process review batch #77", output: "Batch #77 analysis complete. Average sentiment: 0.72 (positive). 42 positive, 5 neutral, 3 negative.", tool: "nlp_engine", risk_score: 83, is_duplicate: true },
      { step_number: 1088, input: "Process review batch #77", output: "Analyzing batch #77... Results: sentiment score 0.72. Distribution: 84% positive, 10% neutral, 6% negative.", tool: "nlp_engine", risk_score: 81, is_duplicate: true },
      { step_number: 1087, input: "Process review batch #77", output: "Batch #77 processed. Overall sentiment: 0.72 (positive). Breakdown: 42/50 positive, 5/50 neutral, 3/50 negative.", tool: "nlp_engine", risk_score: 79, is_duplicate: true },
      { step_number: 1084, input: "Process review batch #76", output: "Batch #76 complete. Average sentiment: 0.65. 38 positive, 8 neutral, 4 negative. Moving to next batch.", tool: "nlp_engine", risk_score: 35, is_duplicate: false },
    ],
  },
  {
    id: "inc-013", agent_id: "17", agent_name: "compliance-checker", incident_type: "error_cascade",
    risk_score_at_kill: 70, steps_before_kill: 678, kill_reason_detail: "Regulatory database connection pool exhausted after agent opened 50 concurrent connections without releasing them. Subsequent compliance checks all failed with connection errors.",
    cost_avoided: 15.40, co2_avoided: 4.0, total_cost_at_kill: 31.78, created_at: h(15),
    snapshot_steps: [
      { step_number: 678, input: "Check regulation compliance for product #2234", output: "ERROR: Connection pool exhausted. Max connections (50) reached. Unable to query regulatory database.", tool: "reg_db", risk_score: 70, is_duplicate: true },
      { step_number: 677, input: "Retry compliance check", output: "ERROR: No available connections. Pool: 50/50 in use. Timeout waiting for connection release.", tool: "reg_db", risk_score: 68, is_duplicate: true },
      { step_number: 676, input: "Verify FDA compliance for batch #889", output: "ERROR: Connection pool limit reached. Cannot establish new database connection.", tool: "reg_db", risk_score: 65, is_duplicate: true },
      { step_number: 630, input: "Begin compliance audit for Q1 product lineup", output: "Starting audit of 200 products against current FDA, EPA, and FTC regulations.", tool: "reg_db", risk_score: 25, is_duplicate: false },
    ],
  },
  {
    id: "inc-014", agent_id: "20", agent_name: "knowledge-base-updater", incident_type: "context_bloat",
    risk_score_at_kill: 66, steps_before_kill: 534, kill_reason_detail: "Agent loaded 340 knowledge base articles into context simultaneously for cross-referencing, consuming 95% of available context window. Each subsequent update required full context reload.",
    cost_avoided: 9.80, co2_avoided: 2.5, total_cost_at_kill: 22.13, created_at: h(10),
    snapshot_steps: [
      { step_number: 534, input: "Cross-reference article #341 with existing knowledge", output: "Loading article #341 into context. Current context: 95% utilized (122,400 / 128,000 tokens). Cross-reference analysis requires full article set.", tool: "kb_loader", risk_score: 66, is_duplicate: false },
      { step_number: 533, input: "Load next article for cross-referencing", output: "Article #340 loaded. Context utilization: 93%. Warning: approaching context limit.", tool: "kb_loader", risk_score: 63, is_duplicate: false },
      { step_number: 200, input: "Update knowledge base with new product docs", output: "Beginning knowledge base update. 340 articles identified for cross-reference validation.", tool: "kb_loader", risk_score: 15, is_duplicate: false },
    ],
  },
  {
    id: "inc-015", agent_id: "3", agent_name: "content-moderator-v2", incident_type: "error_cascade",
    risk_score_at_kill: 59, steps_before_kill: 1203, kill_reason_detail: "Image classification API began returning HTTP 429 (rate limited) errors. Agent queued retries without exponential backoff, causing 200+ failed requests and wasted prompt tokens.",
    cost_avoided: 6.20, co2_avoided: 1.6, total_cost_at_kill: 8.91, created_at: h(20),
    snapshot_steps: [
      { step_number: 1203, input: "Classify image content-45892.jpg", output: "ERROR: HTTP 429 Too Many Requests. Rate limit exceeded. Retry-After: 60s. Retrying immediately...", tool: "image_classifier", risk_score: 59, is_duplicate: true },
      { step_number: 1202, input: "Retry image classification", output: "ERROR: HTTP 429 Too Many Requests. Rate limit will reset in 58s. Retrying...", tool: "image_classifier", risk_score: 57, is_duplicate: true },
      { step_number: 1201, input: "Classify image content-45892.jpg", output: "ERROR: Rate limited by image classification service. Attempt 198.", tool: "image_classifier", risk_score: 55, is_duplicate: true },
      { step_number: 1000, input: "Process moderation queue batch #89", output: "Batch #89: 150 items queued. Beginning classification pipeline.", tool: "image_classifier", risk_score: 18, is_duplicate: false },
    ],
  },
];

export function useIncidents(params: { type?: IncidentType; page?: number; per_page?: number } = {}) {
  const { type, page = 1, per_page = 25 } = params;
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    try {
      const queryParts: string[] = [];
      if (type) queryParts.push(`type=${type}`);
      queryParts.push(`page=${page}`);
      queryParts.push(`per_page=${per_page}`);
      const query = queryParts.length ? `?${queryParts.join("&")}` : "";
      const data = await api.get<IncidentsResponse>(`/api/v1/incidents${query}`);
      // Normalize API response: risk_score may be 0-1, steps field may differ
      const normalized = data.items.map((item: any) => ({
        ...item,
        risk_score_at_kill: item.risk_score_at_kill <= 1
          ? Math.round(item.risk_score_at_kill * 100)
          : item.risk_score_at_kill,
        steps_before_kill: item.steps_before_kill ?? item.steps_at_kill ?? 0,
        cost_avoided: item.cost_avoided ?? 0,
        co2_avoided: item.co2_avoided ?? item.co2_avoided_grams ?? 0,
      }));
      setIncidents(normalized);
      setTotal(data.total);
    } catch {
      let filtered = MOCK_INCIDENTS;
      if (type) filtered = filtered.filter((i) => i.incident_type === type);
      setTotal(filtered.length);
      const start = (page - 1) * per_page;
      setIncidents(filtered.slice(start, start + per_page));
    } finally {
      setLoading(false);
    }
  }, [type, page, per_page]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  return { incidents, total, loading, refetch: fetchIncidents };
}

export function useIncident(id: string) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      setLoading(true);
      try {
        const raw: any = await api.get<Incident>(`/api/v1/incidents/${id}`);
        const data: Incident = {
          ...raw,
          risk_score_at_kill: raw.risk_score_at_kill <= 1
            ? Math.round(raw.risk_score_at_kill * 100)
            : raw.risk_score_at_kill,
          steps_before_kill: raw.steps_before_kill ?? raw.steps_at_kill ?? 0,
          cost_avoided: raw.cost_avoided ?? 0,
          co2_avoided: raw.co2_avoided ?? raw.co2_avoided_grams ?? 0,
        };
        setIncident(data);
      } catch {
        const mock = MOCK_INCIDENTS.find((i) => i.id === id) ?? MOCK_INCIDENTS[0];
        setIncident(mock);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [id]);

  return { incident, loading };
}
