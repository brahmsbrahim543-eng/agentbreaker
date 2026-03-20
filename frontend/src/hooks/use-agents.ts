import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";

export interface Agent {
  id: string;
  external_id: string;
  name: string;
  status: "running" | "warning" | "killed" | "idle";
  current_risk_score: number;
  total_cost: number;
  total_tokens: number;
  total_steps: number;
  total_co2_grams: number;
  total_kwh: number;
  last_seen_at: string;
}

export interface AgentStep {
  step_number: number;
  input: string;
  output: string;
  tool: string | null;
  cost: number;
  tokens: number;
  risk_score: number;
  timestamp: string;
}

interface AgentsResponse {
  items: Agent[];
  total: number;
  page: number;
  per_page: number;
}

interface UseAgentsParams {
  status?: string;
  page?: number;
  per_page?: number;
  search?: string;
}

const now = new Date();
const h = (hours: number) => new Date(now.getTime() - hours * 3600000).toISOString();

const MOCK_AGENTS: Agent[] = [
  { id: "1", external_id: "customer-support-v3", name: "customer-support-v3", status: "running", current_risk_score: 42, total_cost: 12.34, total_tokens: 45000, total_steps: 847, total_co2_grams: 4.8, total_kwh: 0.012, last_seen_at: h(0.1) },
  { id: "2", external_id: "pricing-optimizer", name: "pricing-optimizer", status: "killed", current_risk_score: 92, total_cost: 45.67, total_tokens: 120000, total_steps: 234, total_co2_grams: 12.3, total_kwh: 0.045, last_seen_at: h(2) },
  { id: "3", external_id: "content-moderator-v2", name: "content-moderator-v2", status: "running", current_risk_score: 18, total_cost: 8.91, total_tokens: 32000, total_steps: 1203, total_co2_grams: 3.1, total_kwh: 0.009, last_seen_at: h(0.05) },
  { id: "4", external_id: "email-drafter", name: "email-drafter", status: "warning", current_risk_score: 67, total_cost: 23.45, total_tokens: 89000, total_steps: 456, total_co2_grams: 8.7, total_kwh: 0.032, last_seen_at: h(0.5) },
  { id: "5", external_id: "data-pipeline-orchestrator", name: "data-pipeline-orchestrator", status: "running", current_risk_score: 31, total_cost: 156.78, total_tokens: 450000, total_steps: 3421, total_co2_grams: 45.2, total_kwh: 0.134, last_seen_at: h(0.02) },
  { id: "6", external_id: "fraud-detection-agent", name: "fraud-detection-agent", status: "killed", current_risk_score: 88, total_cost: 34.56, total_tokens: 98000, total_steps: 167, total_co2_grams: 9.4, total_kwh: 0.041, last_seen_at: h(6) },
  { id: "7", external_id: "inventory-manager", name: "inventory-manager", status: "idle", current_risk_score: 5, total_cost: 2.11, total_tokens: 8500, total_steps: 89, total_co2_grams: 0.9, total_kwh: 0.003, last_seen_at: h(48) },
  { id: "8", external_id: "code-reviewer-bot", name: "code-reviewer-bot", status: "running", current_risk_score: 23, total_cost: 67.89, total_tokens: 210000, total_steps: 1567, total_co2_grams: 21.3, total_kwh: 0.078, last_seen_at: h(0.08) },
  { id: "9", external_id: "meeting-summarizer", name: "meeting-summarizer", status: "warning", current_risk_score: 71, total_cost: 19.23, total_tokens: 67000, total_steps: 312, total_co2_grams: 6.5, total_kwh: 0.024, last_seen_at: h(1) },
  { id: "10", external_id: "lead-qualifier", name: "lead-qualifier", status: "running", current_risk_score: 38, total_cost: 41.12, total_tokens: 134000, total_steps: 892, total_co2_grams: 13.1, total_kwh: 0.051, last_seen_at: h(0.3) },
  { id: "11", external_id: "document-parser-v4", name: "document-parser-v4", status: "killed", current_risk_score: 95, total_cost: 89.45, total_tokens: 340000, total_steps: 78, total_co2_grams: 34.1, total_kwh: 0.112, last_seen_at: h(12) },
  { id: "12", external_id: "chatbot-retail", name: "chatbot-retail", status: "running", current_risk_score: 15, total_cost: 5.67, total_tokens: 23000, total_steps: 2145, total_co2_grams: 2.3, total_kwh: 0.007, last_seen_at: h(0.01) },
  { id: "13", external_id: "translation-service", name: "translation-service", status: "idle", current_risk_score: 8, total_cost: 3.22, total_tokens: 12000, total_steps: 156, total_co2_grams: 1.2, total_kwh: 0.004, last_seen_at: h(72) },
  { id: "14", external_id: "report-generator", name: "report-generator", status: "warning", current_risk_score: 58, total_cost: 28.90, total_tokens: 95000, total_steps: 423, total_co2_grams: 9.8, total_kwh: 0.037, last_seen_at: h(0.8) },
  { id: "15", external_id: "sentiment-analyzer", name: "sentiment-analyzer", status: "running", current_risk_score: 27, total_cost: 14.56, total_tokens: 56000, total_steps: 1089, total_co2_grams: 5.6, total_kwh: 0.019, last_seen_at: h(0.15) },
  { id: "16", external_id: "onboarding-assistant", name: "onboarding-assistant", status: "killed", current_risk_score: 81, total_cost: 52.34, total_tokens: 178000, total_steps: 201, total_co2_grams: 17.8, total_kwh: 0.067, last_seen_at: h(4) },
  { id: "17", external_id: "compliance-checker", name: "compliance-checker", status: "running", current_risk_score: 44, total_cost: 31.78, total_tokens: 102000, total_steps: 678, total_co2_grams: 10.2, total_kwh: 0.039, last_seen_at: h(0.2) },
  { id: "18", external_id: "ticket-router", name: "ticket-router", status: "idle", current_risk_score: 3, total_cost: 1.45, total_tokens: 5200, total_steps: 67, total_co2_grams: 0.5, total_kwh: 0.002, last_seen_at: h(96) },
  { id: "19", external_id: "ab-test-evaluator", name: "ab-test-evaluator", status: "warning", current_risk_score: 63, total_cost: 18.90, total_tokens: 71000, total_steps: 345, total_co2_grams: 7.1, total_kwh: 0.026, last_seen_at: h(1.5) },
  { id: "20", external_id: "knowledge-base-updater", name: "knowledge-base-updater", status: "running", current_risk_score: 35, total_cost: 22.13, total_tokens: 83000, total_steps: 534, total_co2_grams: 8.3, total_kwh: 0.031, last_seen_at: h(0.4) },
];

const MOCK_STEPS: AgentStep[] = [
  { step_number: 847, input: "What is the refund policy for order #4521?", output: "The refund policy allows returns within 30 days of purchase. I've located order #4521 and the customer is eligible for a full refund.", tool: "order_lookup", cost: 0.003, tokens: 245, risk_score: 42, timestamp: h(0.1) },
  { step_number: 846, input: "Check if the customer has any previous complaints", output: "Customer has 2 previous complaints in the last 6 months. Both were resolved satisfactorily.", tool: "crm_search", cost: 0.004, tokens: 312, risk_score: 40, timestamp: h(0.12) },
  { step_number: 845, input: "Generate a response email for the customer", output: "Dear valued customer, thank you for reaching out regarding your recent order. We understand your concern and would like to offer you a full refund...", tool: "email_draft", cost: 0.006, tokens: 489, risk_score: 38, timestamp: h(0.15) },
  { step_number: 844, input: "Look up shipping status for order #4519", output: "Order #4519 shipped via FedEx, tracking number 7891234567. Current status: In transit, expected delivery March 19.", tool: "shipping_api", cost: 0.002, tokens: 178, risk_score: 35, timestamp: h(0.2) },
  { step_number: 843, input: "Classify the incoming ticket: 'My product arrived damaged'", output: "Classification: Product Quality > Damaged in Transit. Priority: Medium. Suggested routing: Returns & Exchanges team.", tool: "classifier", cost: 0.002, tokens: 156, risk_score: 33, timestamp: h(0.25) },
  { step_number: 842, input: "Search FAQ for warranty information", output: "Found 3 relevant FAQ articles about warranty coverage. The standard warranty covers manufacturing defects for 12 months from purchase date.", tool: "kb_search", cost: 0.003, tokens: 234, risk_score: 31, timestamp: h(0.3) },
  { step_number: 841, input: "Update ticket #8834 status to 'In Progress'", output: "Ticket #8834 status updated successfully. Assigned to agent: customer-support-v3. SLA timer: 4h remaining.", tool: "ticket_update", cost: 0.001, tokens: 89, risk_score: 29, timestamp: h(0.35) },
  { step_number: 840, input: "Calculate total refund amount including shipping", output: "Product price: 45,99 €, Shipping: 5,99 €, Tax: 4,14 €. Total refund amount: 56,12 €", tool: "calculator", cost: 0.001, tokens: 112, risk_score: 28, timestamp: h(0.4) },
];

export function useAgents(params: UseAgentsParams = {}) {
  const { status, page = 1, per_page = 25, search } = params;
  const [agents, setAgents] = useState<Agent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const queryParts: string[] = [];
      if (status) queryParts.push(`status=${status}`);
      queryParts.push(`page=${page}`);
      queryParts.push(`per_page=${per_page}`);
      const query = queryParts.length ? `?${queryParts.join("&")}` : "";

      const raw = await api.get<AgentsResponse | Agent[]>(`/api/v1/agents${query}`);
      // Normalize risk scores from 0-1 to 0-100 if needed
      const normalizeAgent = (a: Agent): Agent => ({
        ...a,
        current_risk_score: a.current_risk_score <= 1
          ? Math.round(a.current_risk_score * 100)
          : a.current_risk_score,
      });

      // API may return a plain array or {items, total} — handle both
      if (Array.isArray(raw)) {
        let filtered = raw.map(normalizeAgent);
        if (search) {
          const q = search.toLowerCase();
          filtered = filtered.filter((a) => a.name.toLowerCase().includes(q));
        }
        setTotal(filtered.length);
        const start = (page - 1) * per_page;
        setAgents(filtered.slice(start, start + per_page));
      } else {
        setAgents(raw.items.map(normalizeAgent));
        setTotal(raw.total);
      }
    } catch {
      // Fallback to mock data
      let filtered = MOCK_AGENTS;
      if (status) filtered = filtered.filter((a) => a.status === status);
      if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter((a) => a.name.toLowerCase().includes(q));
      }
      setTotal(filtered.length);
      const start = (page - 1) * per_page;
      setAgents(filtered.slice(start, start + per_page));
    } finally {
      setLoading(false);
    }
  }, [status, page, per_page, search]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  return { agents, total, loading, error, refetch: fetchAgents };
}

export function useAgent(id: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      setLoading(true);
      try {
        const data = await api.get<Agent>(`/api/v1/agents/${id}`);
        setAgent({
          ...data,
          current_risk_score: data.current_risk_score <= 1
            ? Math.round(data.current_risk_score * 100)
            : data.current_risk_score,
        });
        const stepsData = await api.get<{ items: AgentStep[] }>(`/api/v1/agents/${id}/steps`);
        setSteps(stepsData.items);
      } catch {
        const mock = MOCK_AGENTS.find((a) => a.id === id) ?? MOCK_AGENTS[0];
        setAgent({ ...mock, id });
        setSteps(MOCK_STEPS);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [id]);

  return { agent, steps, loading };
}
