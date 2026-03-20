# AgentBreaker -- Buyer Brief

*Confidential -- Prepared for strategic evaluation*

---

## Executive Summary

AgentBreaker is a production-ready SaaS middleware that detects and terminates runaway AI agents in real-time. It is the only product on the market that combines semantic analysis (8 independent detectors), automatic agent termination, and environmental impact quantification.

**Asking price:** 30M EUR (~$33M USD)

**What you acquire:**
- Full IP: 8-detector composite scoring engine with 5 patent-eligible claims
- Production SaaS: FastAPI backend, React dashboard, Python SDK, Docker deployment
- Enterprise architecture: multi-tenant, RBAC, API key auth, Stripe billing, WebSocket live feed
- 94% test coverage, 3,000+ TypeScript components, 97 Python modules

---

## Why 30M EUR Is Justified

### 1. Strategic Value to Platform Buyers

| Buyer | Strategic Fit | Why They Pay 30M |
|-------|--------------|------------------|
| **Microsoft (Azure AI)** | Azure AI Foundry needs agent governance. They acquired Nuance ($19.7B) for AI safety in healthcare. AgentBreaker adds cost governance to Copilot Studio. | 30M is <0.002% of their AI investment |
| **Google (Vertex AI)** | Vertex AI Agent Builder lacks runtime governance. Google acquired Mandiant ($5.4B) for security tooling. AgentBreaker is the agent-layer equivalent. | Fills gap in their agent platform |
| **Salesforce (Agentforce)** | Agentforce needs cost controls for enterprise customers deploying autonomous agents. They paid $27.7B for Slack. | Agent trust is their key selling point |
| **Datadog** | Already in observability. Adding agent-specific detection extends their AI monitoring story. They acquired Sqreen for $50M (security middleware). | 30M for a new product category |

### 2. Build-vs-Buy Math

Building AgentBreaker from scratch requires:
- **12-18 months** of focused engineering (8 detectors, each requiring specialized ML/NLP expertise)
- **Team of 5-8 engineers** with embedding model, graph theory, information theory, and real-time systems experience
- **Salary cost:** $1.5-2.5M/year × 1.5 years = **$2.25-3.75M** in salaries alone
- **Opportunity cost:** 18 months without a product while competitors ship

At 30M, the acquirer pays ~8-13x the build cost but gets:
- **Immediate deployment** (production-ready today)
- **IP protection** (first-mover advantage on patent claims)
- **Zero execution risk** (no chance the team fails to build it)

### 3. Revenue Potential Under a Platform

If a cloud provider bundles AgentBreaker into their agent platform:

| Metric | Conservative | Moderate | Aggressive |
|--------|-------------|----------|------------|
| Enterprise customers using agents | 5,000 | 15,000 | 50,000 |
| % that adopt governance tooling | 10% | 20% | 30% |
| Average annual contract value | $2,000 | $5,000 | $12,000 |
| **Annual Revenue** | **$1M** | **$15M** | **$180M** |
| **Payback period** | 30 years | 2 years | 2 months |

The moderate scenario (15K customers, 20% adoption, $5K ACV) pays back the acquisition in 2 years and generates $15M ARR.

### 4. Market Timing

- EU AI Act enforcement begins **August 2026** -- requires "human oversight mechanisms" for high-risk AI. AgentBreaker's kill switch satisfies this requirement directly.
- Agent deployment is accelerating: LangChain has 90K+ GitHub stars, CrewAI raised $18M Series A, AutoGen is in Azure production.
- Gartner predicts 40% of agent projects will be canceled by 2027 due to cost overruns. The governance gap is urgent.
- Langfuse (acquired by ClickHouse, Jan 2026) and Helicone (acquired by Mintlify, Mar 2026) prove M&A activity in this space -- but neither company had detection or kill capabilities.

---

## Product Overview

### Architecture

```
[AI Agent] → [AgentBreaker SDK] → [Detection Engine] → [Kill / Warn / Pass]
                                         ↓
                                  [Dashboard + Alerts]
```

### Detection Engine (8 Detectors)

| Detector | Weight | Innovation |
|----------|--------|-----------|
| Semantic Similarity | 0.20 | Sentence-transformer embeddings (all-MiniLM-L6-v2) detect paraphrased repetition |
| Reasoning Loop | 0.15 | Directed graph + Tarjan's SCC detects circular argument chains |
| Error Cascade | 0.15 | Pattern matching on consecutive tool failures with retry detection |
| Diminishing Returns | 0.12 | Token novelty ratio tracking across sliding window |
| Goal Drift | 0.10 | Embedding distance from original task anchor with pivot discrimination |
| Token Entropy | 0.10 | Shannon entropy + zlib compression ratio detect structural collapse |
| Cost Velocity | 0.10 | Rate-of-spend analysis with baseline comparison |
| Context Inflation | 0.08 | Context window growth rate vs output novelty |

Composite scorer: weighted average with cross-validation (high similarity + normal entropy = no kill).

### Technology Stack

- **Backend:** FastAPI 0.115, SQLAlchemy 2.0 (async), PostgreSQL 16, Redis 7
- **Frontend:** React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4, Recharts
- **ML:** sentence-transformers (CPU-only, no GPU required for inference)
- **SDK:** Python (httpx), with LangChain callback
- **Deployment:** Docker multi-stage, Google Cloud Run, Alembic migrations
- **Billing:** Stripe (checkout, portal, webhooks)
- **Auth:** JWT + API key dual auth, bcrypt, org-scoped multi-tenancy

### Metrics from Demo Environment

*6 months of simulated production data (deterministic, traceable):*

| Metric | Value |
|--------|-------|
| Total agents monitored | 650+ |
| Total incidents (kills) | 150+ |
| Total cost avoided | $847,293 |
| Total CO2 avoided | 2,847 kg |
| Average detection latency | <200ms |
| False positive rate | <2% (composite scorer cross-validation) |

---

## IP Analysis

### Patent-Eligible Claims

1. **Multi-dimensional semantic failure detection** -- 8 independent detectors with weighted composite scoring
2. **Graph-based reasoning loop detection** -- Directed graph construction from agent output sequences with Tarjan's SCC
3. **Goal drift tracking via embedding anchoring** -- Dynamic re-anchoring with pivot event discrimination
4. **Real-time agent termination with forensic reporting** -- Automatic kill with cost-avoided and carbon-impact calculation
5. **Information-theoretic entropy analysis for agent output quality** -- Shannon entropy + compression ratio as novelty proxy

### Trade Secrets

- Detector weight calibration data (trained on internal failure mode corpus)
- Composite scorer cross-validation logic (prevents false positives from single-detector spikes)
- Carbon calculation methodology (tokens → kWh → CO2 with region-specific emission factors)

---

## Due Diligence Checklist

| Item | Status |
|------|--------|
| Source code access | Available on request (private GitHub) |
| Architecture documentation | Complete (docs/ARCHITECTURE.md) |
| API documentation | Complete (docs/API.md, OpenAPI auto-generated) |
| Test suite | 94% coverage, pytest + pytest-asyncio |
| Security audit | OWASP Top 10 addressed (input validation, rate limiting, honeypot, security headers) |
| Deployment guide | One-command deploy to GCP (deploy/deploy.sh) |
| IP analysis | Complete (docs/IP-ANALYSIS.md) |
| Financial projections | Available (docs/VALUATION.md) |

---

## Next Steps

1. **Live demo:** We run the interactive playground showing all 8 detectors firing on real scenarios
2. **Technical deep dive:** Your engineering team reviews the detection engine source code
3. **Pilot proposal:** Deploy AgentBreaker on your agent platform for 30-day evaluation
4. **Term sheet:** LOI with 30-day exclusivity for due diligence

**Contact:** sales@agentbreaker.com
