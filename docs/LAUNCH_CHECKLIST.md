# AgentBreaker -- Launch Checklist

Complete these steps in order. Each step builds on the previous one.

---

## Phase 1: Infrastructure

- [ ] **Deploy backend to Google Cloud Run**
  - Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
  - Authenticate: `gcloud auth login`
  - Create project: `gcloud projects create agentbreaker-prod`
  - Set project: `gcloud config set project agentbreaker-prod`
  - Enable required APIs: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com sqladmin.googleapis.com redis.googleapis.com`
  - Create Cloud SQL (PostgreSQL 16) instance for production database
  - Create Memorystore (Redis 7) instance for WebSocket pub/sub and caching
  - Deploy backend: `gcloud run deploy agentbreaker-api --source ./backend --region europe-west1 --allow-unauthenticated`
  - Deploy frontend: `gcloud run deploy agentbreaker-dashboard --source ./frontend --region europe-west1 --allow-unauthenticated`
  - Verify both services are running and connected

- [ ] **Buy agentbreaker.com domain**
  - Registrar: Namecheap, Google Domains, or Cloudflare (~12 EUR/year)
  - Also grab agentbreaker.dev and agentbreaker.io if available

- [ ] **Point domain to Cloud Run**
  - Map custom domain: `gcloud run domain-mappings create --service agentbreaker-dashboard --domain agentbreaker.com --region europe-west1`
  - Map API subdomain: `gcloud run domain-mappings create --service agentbreaker-api --domain api.agentbreaker.com --region europe-west1`
  - Configure DNS records as instructed by Cloud Run (CNAME or A records)
  - SSL certificates are provisioned automatically by Google

- [ ] **Set up production environment variables**
  - DATABASE_URL pointing to Cloud SQL
  - REDIS_URL pointing to Memorystore
  - JWT_SECRET (generate with `openssl rand -hex 32`)
  - CORS origins set to agentbreaker.com

---

## Phase 2: Open Source and SDK

- [ ] **Create GitHub repository (public)**
  - Repository: `github.com/agentbreaker/agentbreaker`
  - Add the MIT license file
  - Push the full codebase (backend, frontend, SDK, demo, docs)
  - Add GitHub Actions CI pipeline (tests, linting, coverage badge)
  - Write a clean README with quick start, architecture diagram, and demo GIF
  - Add CONTRIBUTING.md with development setup instructions
  - Create issue templates (bug report, feature request)
  - Pin the repo and add topics: `ai-agents`, `llm`, `monitoring`, `kill-switch`, `langchain`

- [ ] **Publish SDK on PyPI**
  - Finalize `sdk/python/pyproject.toml` with metadata (name: `agentbreaker`, version: `0.1.0`)
  - Register on PyPI: https://pypi.org/account/register/
  - Build: `cd sdk/python && python -m build`
  - Upload: `python -m twine upload dist/*`
  - Verify installation: `pip install agentbreaker`
  - Test import: `python -c "from agentbreaker import AgentBreaker; print('OK')"`

---

## Phase 3: Launch

- [ ] **Post on Product Hunt**
  - Create maker account on producthunt.com
  - Schedule launch for a Tuesday or Wednesday (highest traffic days)
  - Use tagline, description, and maker comment from `docs/PRODUCT_HUNT.md`
  - Upload 5 gallery images: dashboard overview, agent detail, incident forensics, playground, SDK code snippet
  - Record a 1-minute demo video (Loom or screen recording) showing a live agent kill
  - Set topics: AI, SaaS, Developer Tools, Cost Optimization
  - Ask 10 people to upvote and leave genuine comments in the first 2 hours
  - Respond to every comment on launch day

- [ ] **Post on HackerNews**
  - Title: "Show HN: AgentBreaker -- Real-time kill switch for AI agents that enter infinite loops"
  - Link to GitHub repo (HN prefers open source links over landing pages)
  - Write a top-level comment explaining the technical approach (8 detectors, embeddings, Tarjan's SCC)
  - Post between 9am-11am EST on a weekday
  - Stay active in comments for the first 6 hours

- [ ] **Post on Reddit**
  - r/MachineLearning: "AgentBreaker: 8 NLP detectors for catching runaway AI agents in real-time" (focus on the technical novelty)
  - r/LangChain: "Built a real-time kill switch for LangChain agents -- 3-line SDK integration" (focus on the integration)
  - r/artificial: broader AI audience
  - r/SideProject: indie builder audience
  - Follow each subreddit's self-promotion rules (some require comment-only, no direct links)

---

## Phase 4: Outreach

- [ ] **Send cold emails to 10 target companies**
  - Use templates from `docs/COLD_EMAIL.md`
  - Priority targets:
    1. Microsoft -- Azure AI Foundry team
    2. Google -- Vertex AI Agent Builder team
    3. Salesforce -- Einstein AI team
    4. Amazon -- AWS Bedrock Agents team
    5. Anthropic -- Claude agent tooling team
    6. OpenAI -- Assistants API team
    7. LangChain -- Harrison Chase (CEO)
    8. CrewAI -- Joao Moura (CEO)
    9. Datadog -- AI monitoring expansion team
    10. New Relic -- AI observability team
  - Find correct contacts via LinkedIn Sales Navigator
  - Send Monday or Tuesday morning (highest open rates)
  - Follow up once after 5 business days if no reply
  - Track opens and replies in a spreadsheet

- [ ] **Create LinkedIn post**
  - Personal post from founder account (not company page -- personal posts get 5-10x reach)
  - Structure: Hook (the $400M problem) > What we built > Why it is different > Link to demo
  - Include 1 image (dashboard screenshot or architecture diagram)
  - Tag relevant people: AI engineering leaders, VC contacts, framework creators
  - Post between 8am-10am local time on Tuesday or Wednesday

---

## Phase 5: IP Protection

- [ ] **File provisional patent application**
  - Focus on Claims 2-4 from `docs/IP-ANALYSIS.md`:
    - Claim 2: Circular reasoning detection via directed graph construction and Tarjan's SCC
    - Claim 3: Goal drift detection via embedding distance tracking with purposeful pivot discrimination
    - Claim 4: Composite risk scoring system for real-time agent termination decisions
  - Provisional patent costs approximately $320 USD (micro entity filing fee)
  - Provides 12 months of patent-pending status
  - Use the IP-ANALYSIS.md document as the technical specification for patent counsel
  - Deadline: File before any public disclosure of the detection algorithms (GitHub repo, blog posts, conference talks)

---

## Phase 6: Metrics to Track After Launch

- [ ] **Set up analytics**
  - GitHub stars and forks (target: 500 stars in first month)
  - PyPI downloads (target: 1,000 installs in first month)
  - Product Hunt upvotes (target: top 5 of the day)
  - HackerNews points (target: front page, 100+ points)
  - Website visitors (Google Analytics or Plausible on agentbreaker.com)
  - Cold email response rate (target: 20%+ reply rate)
  - Demo requests (target: 10 in first two weeks)
  - First paying customer (target: within 60 days of launch)

---

## Timeline

| Week | Focus |
|------|-------|
| Week 1 | Deploy to Cloud Run, buy domain, DNS setup |
| Week 2 | GitHub repo (public), PyPI publish, CI pipeline |
| Week 3 | Product Hunt launch, HackerNews post, Reddit posts |
| Week 4 | Cold emails, LinkedIn post, follow-ups |
| Week 5 | File provisional patent, review metrics, iterate |
