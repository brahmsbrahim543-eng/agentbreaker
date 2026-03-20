# AgentBreaker — Plan d'Implémentation Complet

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** SaaS enterprise-grade qui détecte et kill les agents IA en spirale, sauve l'argent ET le CO2. Vendable à Microsoft/Google à $30M. Preuve live sur vrais agents LangChain/CrewAI.

**Architecture:** Python FastAPI backend async, PostgreSQL + Redis, moteur de détection sémantique 5 détecteurs + carbon calculator, React/TypeScript/Tailwind frontend premium dark mode, SDK Python avec callbacks LangChain/CrewAI, démo live sur vrais agents.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy async, Pydantic v2, Redis, sentence-transformers
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts, Framer Motion
- SDK: Python package, callbacks LangChain + CrewAI
- Démo: LangChain + DuckDuckGo (online) / MockSearchTool (offline)
- Infra: PostgreSQL 16, Redis 7, Docker Compose

---

## Étape 1 — Backend Foundation

### 1.1 — Scaffolding du projet

**Fichiers à créer :**
- `backend/requirements.txt` — toutes les dépendances avec versions exactes
- `backend/.env.example` — DATABASE_URL, REDIS_URL, SECRET_KEY, CORS_ORIGINS
- `backend/app/__init__.py`
- `backend/app/main.py` — app FastAPI avec lifespan (connect DB + Redis au startup, cleanup au shutdown), mount middleware, health check `/health`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py` — Pydantic Settings, toute la config via env vars, zéro secret en dur
- `backend/app/core/database.py` — async engine + async sessionmaker + Base declarative + dependency `get_db()`
- `backend/app/core/redis.py` — connexion Redis, dependency `get_redis()`
- `backend/app/core/security.py` — `create_access_token()`, `verify_token()`, `hash_api_key()`, `verify_api_key()`, hash passwords bcrypt
- `backend/app/core/exceptions.py` — AgentBreakerError, NotFoundError, AuthenticationError, RateLimitError + global exception handler JSON
- `backend/app/core/middleware.py` — RequestLoggingMiddleware (JSON structuré), RateLimitMiddleware (Redis-backed), CORS config

**Résultat :** `uvicorn app.main:app` démarre et répond `{"status": "healthy"}` sur `/health`.

---

### 1.2 — Modèles de base de données

**Fichiers à créer :**
- `backend/app/models/__init__.py` — importe tous les modèles
- `backend/app/models/organization.py` — id (UUID), name, slug, plan (free/pro/enterprise), created_at
- `backend/app/models/user.py` — id, org_id (FK), email, hashed_password, role (admin/member/viewer), created_at
- `backend/app/models/project.py` — id, org_id (FK), name, slug, budget_limit, max_cost_per_agent, max_steps_per_agent, detection_thresholds (JSONB), created_at
- `backend/app/models/api_key.py` — id, project_id (FK), key_prefix, hashed_key, name, is_active, created_at, last_used_at
- `backend/app/models/agent.py` — id, project_id (FK), external_id, name, status (running/warning/killed/idle/completed), current_risk_score, total_cost, total_tokens, total_steps, **total_co2_grams**, **total_kwh**, first_seen_at, last_seen_at
- `backend/app/models/step.py` — id, agent_id (FK), step_number, input_text, output_text, output_embedding (BYTEA), tokens_used, cost, tool_name, duration_ms, context_size, unique_token_ratio, error_message, created_at
- `backend/app/models/incident.py` — id, agent_id (FK), project_id (FK), incident_type (semantic_loop/diminishing_returns/context_bloat/error_cascade/cost_spike/composite), risk_score_at_kill, cost_at_kill, cost_avoided, **co2_avoided_grams**, **kwh_avoided**, steps_at_kill, snapshot (JSONB), kill_reason_detail, created_at
- `backend/app/models/metric.py` — id, project_id (FK), timestamp, active_agents, total_cost, total_savings, total_incidents, **total_co2_saved_grams**, **total_kwh_saved**

**Choix clés :**
- UUIDs partout (pas d'auto-increment) — standard enterprise
- JSONB pour les champs flexibles (thresholds, snapshot)
- CO2 et kWh sur Agent, Incident et Metric — l'écologie est first-class
- Embeddings en BYTEA (numpy sérialisé) — pas besoin de pgvector pour la démo

---

### 1.3 — Migrations Alembic

**Fichiers à créer :**
- `backend/alembic.ini`
- `backend/alembic/env.py` — configuré pour async engine
- `backend/alembic/versions/001_initial.py` — migration générée depuis les modèles

---

### 1.4 — Schemas Pydantic v2

**Fichiers à créer :**
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/organization.py` — OrgCreate, OrgResponse
- `backend/app/schemas/user.py` — UserCreate, UserResponse, UserLogin
- `backend/app/schemas/project.py` — ProjectCreate, ProjectUpdate, ProjectResponse
- `backend/app/schemas/agent.py` — AgentResponse, AgentDetail, AgentList
- `backend/app/schemas/step.py` — StepCreate (ce que le SDK envoie), StepResponse
- `backend/app/schemas/incident.py` — IncidentResponse, IncidentDetail, IncidentSnapshot
- `backend/app/schemas/metric.py` — MetricResponse, MetricTimeline
- `backend/app/schemas/auth.py` — TokenResponse, LoginRequest, RegisterRequest
- `backend/app/schemas/carbon.py` — CarbonImpact (kwh, co2_grams, equivalent_trees, equivalent_km_car, equivalent_phone_charges), CarbonReport
- `backend/app/schemas/detection.py` — RiskScoreBreakdown (5 scores + composite), DetectionResult (score, flag, action), AnalysisResponse (risk + carbon impact)

Tous avec `model_config = ConfigDict(from_attributes=True)`.

---

## Étape 2 — Moteur de Détection (la PI qui vaut $30M)

### 2.1 — Carbon Impact Calculator

**Fichiers à créer :**
- `backend/app/services/__init__.py`
- `backend/app/services/carbon.py`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_carbon.py`

**Ce que je code :**

Constantes basées sur des données réelles :
- Token-to-kWh par classe de modèle (small/medium/large/xl) — basé sur la conso publiée des A100/H100
- Facteur d'émission CO2 par région cloud (us-east: 0.39 kg/kWh, eu-west: 0.23, asia: 0.45, etc.)
- Équivalences : 1 arbre = 22kg CO2/an, 1 km voiture = 120g CO2, 1 charge téléphone = 8.22g CO2

Fonctions :
- `calculate_kwh(tokens, model_class, duration_ms=None) -> float`
- `calculate_co2_grams(kwh, region="us-east") -> float`
- `calculate_equivalences(co2_grams) -> CarbonEquivalences`
- `estimate_avoided_impact(cost_avoided, avg_cost_per_token) -> CarbonImpact`

Tests : vérifier les ranges de kWh, CO2, et que les équivalences sont positives et cohérentes.

---

### 2.2 — Base Detector Interface

**Fichiers à créer :**
- `backend/app/detection/__init__.py`
- `backend/app/detection/base.py`

```python
class BaseDetector(ABC):
    name: str
    weight: float

    @abstractmethod
    async def analyze(self, steps: list[Step]) -> DetectionResult:
        """Retourne score 0-100 et flag optionnel."""
```

---

### 2.3 — Similarity Detector

**Fichiers à créer :**
- `backend/app/detection/similarity.py`
- `backend/tests/test_detection_similarity.py`

**Logique :** Charge `all-MiniLM-L6-v2` (singleton, local). Prend les N derniers outputs (défaut: 3). Calcule les embeddings. Cosine similarity pairwise. Score = mean_similarity × 100. Si > 85 → flag `semantic_loop`.

**Tests :**
- 3 outputs identiques → score > 90 ✓
- 3 outputs paraphrasés ("The answer is 42" / "42 is the answer" / "The result is 42") → score > 80 ✓
- 3 outputs complètement différents → score < 30 ✓

---

### 2.4 — Diminishing Returns Scorer

**Fichiers à créer :**
- `backend/app/detection/diminishing_returns.py`
- `backend/tests/test_detection_diminishing.py`

**Logique :** Track les tokens uniques par step. Ratio = new_unique_tokens / total_tokens. Score = 100 - (avg_ratio × 100). Si ratio < 0.1 → flag `diminishing_returns`.

**Tests :**
- Steps qui répètent les mêmes mots → score haut ✓
- Steps avec beaucoup de vocabulaire nouveau → score bas ✓

---

### 2.5 — Context Inflation Monitor

**Fichiers à créer :**
- `backend/app/detection/context_inflation.py`
- `backend/tests/test_detection_context.py`

**Logique :** Track context_size par step. Si croissance > 20% par step sans changement d'output → flag `context_bloat`. Score basé sur le taux de croissance vs la nouveauté de l'output.

---

### 2.6 — Error Cascade Detector

**Fichiers à créer :**
- `backend/app/detection/error_cascade.py`
- `backend/tests/test_detection_error.py`

**Logique :** Track error_message et tool_name par step. Même outil qui fail 3+ fois de suite, ou même erreur qui se répète → flag `error_cascade`. Score basé sur le nombre de failures consécutives.

---

### 2.7 — Cost Velocity Tracker

**Fichiers à créer :**
- `backend/app/detection/cost_velocity.py`
- `backend/tests/test_detection_cost.py`

**Logique :** $/seconde sur fenêtre glissante (60s). Compare à la baseline (moyenne des 5 dernières minutes). Si vélocité > 3× baseline → flag `cost_spike`. Score basé sur le ratio d'accélération.

---

### 2.8 — Composite Scorer + Kill Engine

**Fichiers à créer :**
- `backend/app/detection/composite.py`
- `backend/app/detection/engine.py`
- `backend/tests/test_detection_composite.py`
- `backend/tests/test_detection_engine.py`

**Composite Scorer :**
- Prend les 5 résultats de détection
- Poids configurables (défaut : similarity 0.30, diminishing 0.20, context 0.15, error 0.20, cost 0.15)
- Retourne score pondéré 0-100

**Engine :**
- `analyze_step(agent_id, step_data) -> AnalysisResult`
- Lance les 5 détecteurs en parallèle (`asyncio.gather`)
- Calcule le composite score
- Si score > kill_threshold (défaut 75) : déclenche le kill → crée Incident + snapshot + calcule CO2 évité
- Retourne : risk_breakdown, composite_score, action (none/warn/kill), carbon_impact

---

## Étape 3 — Routes API

### 3.1 — Auth

**Fichiers à créer :**
- `backend/app/api/__init__.py`
- `backend/app/api/v1/__init__.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/deps.py` — dependencies: `get_current_user()`, `get_current_org()`, `verify_api_key()`
- `backend/app/api/v1/routes/auth.py`
- `backend/app/services/auth.py`

**Endpoints :**
- `POST /api/v1/auth/register` — crée org + admin user
- `POST /api/v1/auth/login` — retourne JWT
- `GET /api/v1/auth/me` — info user courant

---

### 3.2 — Projects + API Keys

**Fichiers à créer :**
- `backend/app/api/v1/routes/projects.py`
- `backend/app/api/v1/routes/api_keys.py`
- `backend/app/services/projects.py`
- `backend/app/services/api_keys.py`

**Endpoints :**
- CRUD projets (scoped par org)
- `POST /api/v1/projects/{id}/api-keys` — génère une clé (retourne en clair UNE SEULE FOIS, stocke le hash)
- `DELETE /api/v1/projects/{id}/api-keys/{key_id}` — révoque
- `GET /api/v1/projects/{id}/api-keys` — liste (préfixe seulement)

---

### 3.3 — Ingest (endpoint SDK)

**Fichiers à créer :**
- `backend/app/api/v1/routes/ingest.py`
- `backend/app/services/ingest.py`

**LE endpoint critique :**
- `POST /api/v1/ingest/step` — le SDK envoie un step ici
  1. Valide l'API key
  2. Crée/met à jour l'agent
  3. Stocke le step
  4. Lance le moteur de détection
  5. Retourne : `{ risk_score, action, warnings, carbon_impact }`
  6. Si action == "kill" → le SDK reçoit le signal et stoppe l'agent

---

### 3.4 — Agents

**Fichiers à créer :**
- `backend/app/api/v1/routes/agents.py`
- `backend/app/services/agents.py`

**Endpoints :**
- `GET /api/v1/agents` — liste (filtrable par status, risk range)
- `GET /api/v1/agents/{id}` — détail avec risk breakdown complet

---

### 3.5 — Incidents

**Fichiers à créer :**
- `backend/app/api/v1/routes/incidents.py`
- `backend/app/services/incidents.py`

**Endpoints :**
- `GET /api/v1/incidents` — liste (filtrable par type, date, agent)
- `GET /api/v1/incidents/{id}` — détail avec snapshot complet
- `GET /api/v1/incidents/{id}/export` — export JSON
- `GET /api/v1/incidents/stats` — stats agrégées

---

### 3.6 — Analytics + Carbon Report

**Fichiers à créer :**
- `backend/app/api/v1/routes/analytics.py`
- `backend/app/services/analytics.py`

**Endpoints :**
- `GET /api/v1/analytics/overview` — KPIs (savings, agents actifs, incidents, avg risk, **CO2 saved**)
- `GET /api/v1/analytics/savings-timeline` — coût saved par jour (area chart)
- `GET /api/v1/analytics/top-agents` — top 10 plus coûteux (bar chart)
- `GET /api/v1/analytics/incident-distribution` — breakdown par type (donut)
- `GET /api/v1/analytics/carbon-report` — **rapport écologique complet** (kWh, CO2, équivalences, trend mensuel)
- `GET /api/v1/analytics/heatmap` — activité par heure (GitHub-style)

---

### 3.7 — Settings

**Fichiers à créer :**
- `backend/app/api/v1/routes/settings.py`
- `backend/app/services/settings.py`

**Endpoints :**
- `GET/PUT /api/v1/settings/detection` — seuils par projet
- `GET/PUT /api/v1/settings/budget` — limits budget
- `GET/PUT /api/v1/settings/notifications` — config notifications

---

### 3.8 — Playground (simulation live)

**Fichiers à créer :**
- `backend/app/api/v1/routes/playground.py`
- `backend/app/services/playground.py`

**Endpoints :**
- `GET /api/v1/playground/scenarios` — liste les 3 scénarios
- `POST /api/v1/playground/simulate` — lance une simulation
- `WS /api/v1/ws/playground/{session_id}` — WebSocket qui stream les events en temps réel

**Logique :** Génère des fake steps à 1-2s d'intervalle, les passe dans le VRAI moteur de détection, le risk score monte, warnings apparaissent, puis KILL.

---

### 3.9 — WebSocket Live Feed

**Fichiers à créer :**
- `backend/app/api/v1/routes/ws.py`

**Endpoint :**
- `WS /api/v1/ws/live` — stream temps réel de tous les events (agent_started, warning, killed, co2_saved) vers le dashboard

---

### 3.10 — Assemblage + Test d'intégration

**Fichiers à modifier :**
- `backend/app/api/v1/router.py` — monte toutes les routes

**Test d'intégration :**
- `backend/tests/test_integration.py` — crée org → projet → API key → envoie 10 steps qui escaladent → vérifie que le risk score monte → vérifie que le kill fire → vérifie que l'incident est créé avec les données CO2

---

## Étape 4 — Seed Data

### 4.1 — Script de génération

**Fichier à créer :**
- `backend/scripts/seed.py`

**Génère (seed fixe = 42, déterministe) :**

| Donnée | Volume |
|---|---|
| Organisations | 3 (TechCorp AI, FinanceBot Inc, HealthAgent Labs) |
| Users | 1 demo user par org (demo@techcorp.ai, mot de passe: demo123) |
| Projets | 1-2 par org avec seuils configurés |
| Agents | ~650 avec noms réalistes par catégorie (support, finance, dev, legal, data) |
| Incidents | ~150 sur 180 jours (plus en semaine, 45% semantic_loop, 25% error_cascade, 15% cost_spike, 10% diminishing_returns, 5% context_bloat) |
| Cost avoided total | $847,293 |
| CO2 avoided total | ~2,847 kg |
| Métriques horaires | 180 jours avec courbe d'adoption croissante |

---

## Étape 5 — Frontend Setup + Design System

### 5.1 — Initialisation du projet

**Fichiers à créer :**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tailwind.config.ts`
- `frontend/postcss.config.js`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles/globals.css`

Vite + React + TypeScript. Dépendances : tailwindcss, @radix-ui/*, recharts, framer-motion, lucide-react, clsx, tailwind-merge, react-router-dom.

Tailwind configuré avec dark mode, couleurs custom, fonts Inter + JetBrains Mono.

---

### 5.2 — Design System + Composants de base

**Fichiers à créer :**
- `frontend/src/lib/utils.ts` — helper `cn()` pour les classes conditionnelles
- `frontend/src/lib/api.ts` — wrapper fetch avec auth JWT, base URL, error handling
- `frontend/src/components/ui/card.tsx` — glassmorphism (backdrop-blur, border subtle)
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/table.tsx`
- `frontend/src/components/ui/skeleton.tsx`
- `frontend/src/components/ui/slider.tsx`
- `frontend/src/components/ui/tabs.tsx`
- `frontend/src/components/layout/sidebar.tsx` — nav items: Overview, Agents, Incidents, Analytics, Playground, Settings
- `frontend/src/components/layout/header.tsx`
- `frontend/src/components/layout/layout.tsx`

**Tokens de design :**
```
Background:      #0A0A0F
Surface:         #111118
Surface Hover:   #1A1A24
Border:          rgba(255,255,255,0.06)
Text Primary:    #F5F5F7
Text Secondary:  #8B8B9E
Accent Cyan:     #00D4FF
Accent Green:    #10B981
Accent Red:      #EF4444
Accent Yellow:   #F59E0B
```

---

## Étape 6 — Pages du Dashboard

### 6.1 — Overview

**Fichiers à créer :**
- `frontend/src/pages/overview.tsx`
- `frontend/src/components/dashboard/kpi-card.tsx`
- `frontend/src/components/dashboard/savings-chart.tsx`
- `frontend/src/components/dashboard/live-feed.tsx`
- `frontend/src/components/dashboard/activity-heatmap.tsx`
- `frontend/src/components/dashboard/carbon-banner.tsx`
- `frontend/src/hooks/use-analytics.ts`

**Contenu :**
1. 4 KPI cards : Money Saved ($847,293), Active Agents (2,847), Incidents Today (23), **CO2 Saved (2,847 kg)**
2. **Bannière Carbon Impact** — "Equivalent to X trees planted | X km driving avoided | X phone charges" — fond gradient vert
3. Area chart — savings 30 jours avec **toggle Cost / CO2**
4. Live Feed — events temps réel (🟢 started, 🟡 warning, 🔴 killed, 🌿 co2_saved)
5. Heatmap d'activité — style GitHub, 12 dernières semaines

---

### 6.2 — Agents

**Fichiers à créer :**
- `frontend/src/pages/agents.tsx`
- `frontend/src/pages/agent-detail.tsx`
- `frontend/src/components/agents/agents-table.tsx`
- `frontend/src/components/agents/risk-bar.tsx`
- `frontend/src/components/agents/agent-timeline.tsx`
- `frontend/src/hooks/use-agents.ts`

Table : Name, Status (dot coloré), Risk Score (barre 0-100), Total Cost, Steps, CO2 (grams), Last Active. Search + filters. Click → détail avec trace complète + graphe risk over time.

---

### 6.3 — Incidents

**Fichiers à créer :**
- `frontend/src/pages/incidents.tsx`
- `frontend/src/pages/incident-detail.tsx`
- `frontend/src/components/incidents/incidents-list.tsx`
- `frontend/src/components/incidents/incident-snapshot.tsx`
- `frontend/src/components/incidents/risk-timeline.tsx`
- `frontend/src/hooks/use-incidents.ts`

Liste : timestamp, agent, type (badge), coût évité, CO2 évité, durée avant kill. Détail : snapshot des 10 derniers steps, outputs répétés surlignés, graphe du risk qui monte jusqu'au kill.

---

### 6.4 — Analytics + Sustainability Report

**Fichiers à créer :**
- `frontend/src/pages/analytics.tsx`
- `frontend/src/components/analytics/top-agents-chart.tsx`
- `frontend/src/components/analytics/incident-donut.tsx`
- `frontend/src/components/analytics/cost-trend.tsx`
- `frontend/src/components/analytics/sustainability-report.tsx`
- `frontend/src/hooks/use-analytics-detail.ts`

Sections : Top 10 agents (bar chart) + donut incidents + trend 90 jours + **Sustainability Report** (kWh total, CO2 total, équivalences, trend mensuel, bouton "Download ESG Report").

---

### 6.5 — Settings

**Fichiers à créer :**
- `frontend/src/pages/settings.tsx`
- `frontend/src/components/settings/detection-thresholds.tsx`
- `frontend/src/components/settings/budget-limits.tsx`
- `frontend/src/components/settings/notifications.tsx`
- `frontend/src/components/settings/api-keys.tsx`
- `frontend/src/components/settings/team.tsx`

5 onglets : Detection (5 sliders + composite), Budget (limits), Notifications (email/Slack/PagerDuty), API Keys (create/revoke/copy), Team (invite/rôles).

---

### 6.6 — Playground

**Fichiers à créer :**
- `frontend/src/pages/playground.tsx`
- `frontend/src/components/playground/scenario-card.tsx`
- `frontend/src/components/playground/simulation-view.tsx`
- `frontend/src/components/playground/live-risk-gauge.tsx`
- `frontend/src/hooks/use-playground.ts`

3 scénarios :
1. "Semantic Loop" — agent reformule → détecté step 5 → kill → $12.40 + 3.2g CO2 saved
2. "Cost Explosion" — agent spam API → cost spike → kill → $47.80 + 15.1g CO2 saved
3. "Error Cascade" — agent retry en boucle → error cascade → kill → $8.90 + 2.8g CO2 saved

Click "Run Demo" → WebSocket → risk gauge animée (vert→jaune→rouge) → log des steps comme un terminal → warnings → KILL (flash rouge) → affiche savings. Bouton "Run Again".

---

### 6.7 — Routing + Auth

**Fichiers à créer :**
- `frontend/src/lib/router.tsx`
- `frontend/src/contexts/auth-context.tsx`
- `frontend/src/pages/login.tsx`

Routes : `/login`, `/overview`, `/agents`, `/agents/:id`, `/incidents`, `/incidents/:id`, `/analytics`, `/playground`, `/settings`. Routes protégées avec auth context. Login auto-fill pour la démo.

---

## Étape 7 — Landing Page

### 7.1 — Page publique

**Fichiers à créer :**
- `landing/package.json`
- `landing/index.html`
- `landing/src/main.tsx`
- `landing/src/pages/landing.tsx`
- `landing/src/components/hero.tsx` — "Stop burning money on runaway AI agents. Save the planet." + animation agent spiral + CTA
- `landing/src/components/problem-stats.tsx` — "$400M lost", "73% over budget", "40% canceled" — compteurs animés au scroll
- `landing/src/components/how-it-works.tsx` — Install SDK → Monitor → Auto-Kill — 3 colonnes
- `landing/src/components/green-ai.tsx` — **Section écologique** : stats CO2, équivalences, mention ESG compliance — visuellement frappant, accent vert
- `landing/src/components/pricing.tsx` — Free ($0) / Pro ($49/mo) / Enterprise ($499/mo, inclut ESG reports)
- `landing/src/components/code-snippet.tsx` — `pip install agentbreaker`, bloc de code dark
- `landing/src/components/footer.tsx` — "Built with 🧠 for responsible AI"

---

## Étape 8 — SDK Python + Callbacks LangChain/CrewAI

### 8.1 — Package SDK

**Fichiers à créer :**
- `sdk/python/agentbreaker/__init__.py`
- `sdk/python/agentbreaker/client.py` — classe `AgentBreaker` avec `track_step()`, sync + async, retries avec backoff, gestion du signal kill
- `sdk/python/agentbreaker/callbacks.py` — `AgentBreakerLangChainCallback(BaseCallbackHandler)` + `AgentBreakerCrewAICallback`
- `sdk/python/agentbreaker/exceptions.py` — `AgentKilledError`, `AgentBreakerAPIError`
- `sdk/python/agentbreaker/types.py` — `StepResult`, `RiskAssessment`, `CarbonImpact`
- `sdk/python/setup.py` — package installable
- `sdk/python/README.md`
- `sdk/python/tests/test_client.py`

**Usage :**
```python
from agentbreaker import AgentBreaker
ab = AgentBreaker(api_key="ab_live_xxx", project="my-project")
result = ab.track_step(agent_id="agent-1", input=prompt, output=response, tokens=150, cost=0.003)
# result.action == "kill" → lever AgentKilledError
```

**Callback LangChain :**
```python
from agentbreaker.callbacks import AgentBreakerLangChainCallback
callback = AgentBreakerLangChainCallback(ab, agent_id="research-agent")
agent.run("Find the number of stars", callbacks=[callback])
# → si l'agent spirale, AgentBreaker le kill automatiquement
```

---

## Étape 9 — Démo Live sur Vrais Agents

### 9.1 — Mock Search Tool (fallback offline)

**Fichier à créer :**
- `demo/mock_tools.py`

```python
class MockSearchTool:
    """Simule DuckDuckGo avec résultats légèrement différents à chaque appel.
    Assez similaires pour que le Similarity Detector les catch.
    Seed fixe → résultats reproductibles pour la vidéo."""

    def __init__(self, seed=42):
        self.call_count = 0
        self.rng = random.Random(seed)

    def search(self, query: str) -> str:
        self.call_count += 1
        # Résultats sur le même sujet, reformulés :
        # Call 1: "Scientists estimate roughly 200 billion trillion stars..."
        # Call 2: "Astronomers believe approximately 200 sextillion stars..."
        # Call 3: "Current estimates suggest around 2×10²³ stars exist..."
```

---

### 9.2 — Scripts de démo live

**Fichiers à créer :**
- `demo/requirements.txt` — langchain, duckduckgo-search, crewai, agentbreaker
- `demo/scenario_semantic_loop.py` — agent LangChain + DuckDuckGo/Mock, tâche impossible ("Find the exact number of stars in the universe and verify from 3 sources")
- `demo/scenario_error_cascade.py` — agent LangChain + faux outil qui fail, retry en boucle
- `demo/scenario_cost_explosion.py` — multi-agent CrewAI qui se délèguent en cercle
- `demo/run_demo.py` — lance un scénario au choix avec switch online/offline

**Chaque script :**
1. Démarre le backend en arrière-plan (ou se connecte au backend déjà lancé)
2. Crée un agent LangChain/CrewAI avec le callback AgentBreaker branché
3. Lance la tâche
4. L'agent spirale → le moteur détecte → risk score monte → KILL
5. Affiche dans le terminal : chaque step, le risk score, les warnings, le kill final avec $X saved + Xg CO2 saved

**Switch online/offline :**
```python
if os.getenv("AGENTBREAKER_OFFLINE"):
    search_tool = MockSearchTool()
else:
    search_tool = DuckDuckGoSearchTool()
```

---

### 9.3 — Setup pour l'enregistrement vidéo

**Ce qu'on filme (écran splitté) :**
- **Gauche :** terminal — l'agent qui tourne, on voit les steps, les recherches, les reformulations
- **Moitié droite :** dashboard dans le navigateur — live feed, risk score qui monte en temps réel
- **Le kill :** score passe le seuil → dashboard flashe rouge → terminal affiche `AgentKilledError` → KPIs se mettent à jour

**Enregistrement :** OBS Studio (gratuit) ou screen record Windows. 2 min par scénario. Pas de montage — la réaction brute du système est la preuve.

---

## Étape 10 — Infrastructure + Qualité

### 10.1 — Docker Compose

**Fichier à créer :**
- `docker-compose.yml`

4 services : postgres (16, healthcheck), redis (7, healthcheck), backend (FastAPI, lance migrations + seed au premier démarrage), frontend (Vite dev ou nginx prod).

`docker-compose up` → tout tourne.

---

### 10.2 — Tests

**Fichiers à créer :**
- `backend/tests/conftest.py` — fixtures : test DB, test client, test API key
- `backend/tests/test_api_auth.py`
- `backend/tests/test_api_ingest.py`
- `backend/tests/test_api_agents.py`
- `backend/tests/test_api_incidents.py`
- Tests du moteur de détection (déjà créés en étape 2)
- Tests du carbon calculator (déjà créé en étape 2)

Coverage minimum : moteur de détection 100%, carbon calculator 100%, endpoints critiques (ingest, auth).

---

### 10.3 — Documentation

**Fichiers à créer :**
- `README.md` — overview, diagramme architecture (mermaid), setup instructions, quick start
- `docs/ARCHITECTURE.md` — choix techniques justifiés face à un CTO
- `docs/API.md` — tous les endpoints avec exemples curl
- `docs/CARBON-METHODOLOGY.md` — **comment on calcule le CO2** : sources des facteurs d'émission, références scientifiques, méthodologie. Crucial pour la crédibilité ESG auprès des acheteurs.

---

### 10.4 — CI GitHub Actions

**Fichier à créer :**
- `.github/workflows/ci.yml`

Jobs : lint (black + isort + eslint + prettier), test (pytest avec postgres service container), build (docker build), type check (mypy + tsc).

---

## Résumé Final

| Étape | Quoi | Fichiers | Dépend de |
|---|---|---|---|
| 1 | Backend foundation | ~25 | — |
| 2 | Moteur de détection + carbon | ~15 | Étape 1 |
| 3 | Routes API + WebSocket | ~25 | Étapes 1, 2 |
| 4 | Seed data | ~2 | Étapes 1, 2, 3 |
| 5 | Frontend setup + design system | ~15 | — (parallélisable) |
| 6 | Pages du dashboard | ~35 | Étapes 4, 5 |
| 7 | Landing page | ~12 | — (parallélisable) |
| 8 | SDK + callbacks LangChain/CrewAI | ~10 | Étape 3 |
| 9 | **Démo live sur vrais agents** | ~5 | Étapes 6, 8 |
| 10 | Docker + tests + docs + CI | ~15 | Tout |
| **TOTAL** | | **~159 fichiers** | |

## Ce qui rend ce produit vendable à $30M

1. **Détection sémantique** — pas un compteur, de la vraie NLP sur les outputs
2. **Carbon Impact first-class** — kWh/CO2 à chaque niveau, rapport ESG téléchargeable
3. **Preuve live** — vidéo 2 min d'un vrai agent LangChain qui se fait kill
4. **Fallback offline** — démo reproductible sans internet
5. **UI premium** — niveau Linear/Vercel, dark mode, animations
6. **SDK 3 lignes** — intégration sans friction
7. **Code audit-ready** — typé, testé, documenté, dockerisé
