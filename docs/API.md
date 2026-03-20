# AgentBreaker -- API Reference

**Base URL:** `http://localhost:8000/api/v1`

**API Version:** v1

## Authentication

AgentBreaker uses two authentication mechanisms depending on the caller:

### JWT Tokens (Dashboard)

Used by the React dashboard and any browser-based client. Obtained via the `/auth/login` or `/auth/register` endpoints.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

JWT tokens contain `sub` (user ID) and `org` (organization ID) claims. Default expiry is 24 hours. All dashboard endpoints require a valid JWT.

### API Keys (SDK)

Used by the Python SDK and any programmatic integration. Created via the `/projects/{id}/api-keys` endpoint.

```
X-API-Key: ab_live_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
```

API keys are scoped to a specific project. The key prefix (`ab_live_` + first 8 hex chars) is stored for identification; the full key is hashed with SHA-256 at rest. Only the ingest endpoints accept API key authentication.

### Error Responses

All error responses follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Validation error (invalid request body or parameters) |
| 401 | Missing or invalid authentication |
| 403 | Authenticated but not authorized for this resource |
| 404 | Resource not found |
| 422 | Unprocessable entity (Pydantic validation failure) |
| 429 | Rate limit exceeded (100 requests/minute per key or IP) |
| 500 | Internal server error |

---

## Auth

### POST /auth/register

Create a new organization and admin user.

**Auth:** None

**Request:**

```json
{
  "org_name": "Acme Corp",
  "email": "admin@acme.com",
  "password": "securePassword123"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| org_name | string | yes | 2-100 characters |
| email | string | yes | Valid email format |
| password | string | yes | Minimum 8 characters |

**Response (201):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Email already registered |
| 422 | Missing required field or invalid format |

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"org_name":"Acme Corp","email":"admin@acme.com","password":"securePassword123"}'
```

---

### POST /auth/login

Authenticate with email and password.

**Auth:** None

**Request:**

```json
{
  "email": "admin@acme.com",
  "password": "securePassword123"
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Errors:**

| Status | Cause |
|--------|-------|
| 401 | Invalid email or password |

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"securePassword123"}'
```

---

### GET /auth/me

Return the current user profile with organization info.

**Auth:** JWT

**Response (200):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "admin@acme.com",
  "role": "admin",
  "created_at": "2025-03-15T10:30:00",
  "organization": {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "pro",
    "created_at": "2025-03-15T10:30:00"
  }
}
```

**curl:**

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <jwt>"
```

---

## Projects

### GET /projects

List all projects in the current organization.

**Auth:** JWT

**Response (200):**

```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "org_id": "660e8400-e29b-41d4-a716-446655440000",
    "name": "Production Agents",
    "slug": "production-agents",
    "budget_limit": 500.0,
    "max_cost_per_agent": 10.0,
    "max_steps_per_agent": 100,
    "detection_thresholds": {
      "kill_threshold": 75,
      "warn_threshold": 50,
      "similarity": 85
    },
    "carbon_region": "us-east",
    "created_at": "2025-03-15T10:30:00",
    "updated_at": "2025-03-15T10:30:00"
  }
]
```

**curl:**

```bash
curl http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer <jwt>"
```

---

### POST /projects

Create a new project.

**Auth:** JWT

**Request:**

```json
{
  "name": "Production Agents",
  "budget_limit": 500.0,
  "max_cost_per_agent": 10.0,
  "max_steps_per_agent": 100,
  "detection_thresholds": {
    "kill_threshold": 75,
    "warn_threshold": 50
  },
  "carbon_region": "us-east"
}
```

| Field | Type | Required | Default |
|-------|------|----------|---------|
| name | string | yes | -- |
| budget_limit | float | no | null |
| max_cost_per_agent | float | no | null |
| max_steps_per_agent | int | no | null |
| detection_thresholds | object | no | null |
| carbon_region | string | no | "us-east" |

**Response (201):** Same as project object above.

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Production Agents","budget_limit":500.0,"carbon_region":"us-east"}'
```

---

### GET /projects/{project_id}

Get a specific project.

**Auth:** JWT

**Response (200):** Project object.

**Errors:**

| Status | Cause |
|--------|-------|
| 404 | Project not found |
| 403 | Project belongs to another organization |

---

### PUT /projects/{project_id}

Update an existing project. Only provided fields are updated.

**Auth:** JWT

**Request:**

```json
{
  "name": "Staging Agents",
  "budget_limit": 100.0
}
```

All fields are optional. Same schema as `POST /projects`.

**Response (200):** Updated project object.

---

## API Keys

### POST /projects/{project_id}/api-keys

Generate a new API key for a project. The plain-text key is returned exactly once.

**Auth:** JWT

**Request:**

```json
{
  "name": "Production SDK Key"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| name | string | yes | 1-100 characters |

**Response (201):**

```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "name": "Production SDK Key",
  "key": "ab_live_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "key_prefix": "ab_live_a1b2c3d4",
  "created_at": "2025-03-15T10:30:00"
}
```

**Important:** The `key` field is the full API key. Store it securely. It will not be returned again.

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/projects/770e8400-.../api-keys \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Production SDK Key"}'
```

---

### GET /projects/{project_id}/api-keys

List all API keys for a project. Returns prefixes only, never the full key.

**Auth:** JWT

**Response (200):**

```json
[
  {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "name": "Production SDK Key",
    "key_prefix": "ab_live_a1b2c3d4",
    "is_active": true,
    "created_at": "2025-03-15T10:30:00",
    "last_used_at": "2025-03-18T14:22:00"
  }
]
```

---

### DELETE /projects/{project_id}/api-keys/{key_id}

Revoke an API key. Sets `is_active` to false. The key will be rejected on subsequent requests.

**Auth:** JWT

**Response:** 204 No Content

**Errors:**

| Status | Cause |
|--------|-------|
| 404 | API key not found |
| 403 | Project belongs to another organization |

**curl:**

```bash
curl -X DELETE http://localhost:8000/api/v1/projects/770e.../api-keys/880e... \
  -H "Authorization: Bearer <jwt>"
```

---

## Ingest

### POST /ingest/step

Ingest a single agent step and receive real-time risk analysis. This is the primary endpoint used by the SDK.

**Auth:** API Key (`X-API-Key` header)

**Request:**

```json
{
  "agent_id": "order-bot-session-42",
  "input": "Find the cheapest flight from SFO to NRT",
  "output": "Searching across 3 flight providers: Expedia, Google Flights, Kayak...",
  "tokens": 250,
  "cost": 0.0075,
  "tool": "web_search",
  "duration_ms": 1200,
  "context_size": 4096,
  "error_message": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent_id | string | yes | Unique identifier for the agent session. Agents are auto-created on first step. |
| input | string | yes | The prompt or input given to the agent at this step. |
| output | string | yes | The agent's response or output. |
| tokens | int | yes | Number of tokens consumed (>= 0). |
| cost | float | yes | Dollar cost of this step (>= 0). |
| tool | string | no | Name of the tool invoked, if any. Used by error cascade detector. |
| duration_ms | int | no | Wall-clock duration of the step in milliseconds. |
| context_size | int | no | Current context window size in tokens. Used by context inflation detector. |
| error_message | string | no | Error string if the step failed. Used by error cascade detector. |

**Response (200):**

```json
{
  "step_number": 7,
  "risk_score": 62.4,
  "risk_breakdown": {
    "similarity": 78.2,
    "diminishing_returns": 65.0,
    "context_inflation": 32.1,
    "error_cascade": 0.0,
    "cost_velocity": 45.3,
    "composite": 62.4
  },
  "action": "warn",
  "warnings": [
    "Mean pairwise similarity 0.782 across 3 outputs",
    "Avg novelty ratio 0.053 over 4 transitions"
  ],
  "carbon_impact": {
    "kwh": 0.0005,
    "co2_grams": 0.195,
    "equivalent_trees": 0.0000089,
    "equivalent_km_car": 0.001625,
    "equivalent_phone_charges": 0.0237
  }
}
```

| Response Field | Description |
|---------------|-------------|
| step_number | Sequential step number for this agent session. |
| risk_score | Composite risk score (0-100). |
| risk_breakdown | Individual scores from each detector plus the composite. |
| action | `"ok"` (score < 50), `"warn"` (50-74), or `"kill"` (>= 75). |
| warnings | Human-readable strings from detectors that scored above 30. |
| carbon_impact | Environmental impact of this step. Null if carbon calculation is not configured. |

**Action thresholds (configurable per project):**

| Action | Default Threshold | SDK Behavior |
|--------|------------------|--------------|
| `ok` | score < 50 | Continue normally |
| `warn` | 50 <= score < 75 | Log warning, continue |
| `kill` | score >= 75 | SDK raises `AgentKilledError`, incident is created |

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/ingest/step \
  -H "X-API-Key: ab_live_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "order-bot-session-42",
    "input": "Find cheapest flight",
    "output": "Searching flights...",
    "tokens": 150,
    "cost": 0.004
  }'
```

---

## Agents

### GET /agents

List agents across all projects in the organization with filters, sorting, and pagination.

**Auth:** JWT

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | null | Filter by status: `running`, `warning`, `killed`, `idle`, `completed` |
| risk_min | float | null | Minimum risk score (0-100) |
| risk_max | float | null | Maximum risk score (0-100) |
| sort_by | string | `last_seen_at` | Sort field: `last_seen_at`, `current_risk_score`, `total_cost`, `total_steps` |
| sort_order | string | `desc` | Sort direction: `asc`, `desc` |
| page | int | 1 | Page number (>= 1) |
| per_page | int | 20 | Items per page (1-100) |

**Response (200):**

```json
{
  "items": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "external_id": "order-bot-session-42",
      "name": "order-bot-session-42",
      "status": "warning",
      "current_risk_score": 62.4,
      "total_cost": 0.35,
      "total_tokens": 12500,
      "total_steps": 7,
      "total_co2_grams": 4.87,
      "total_kwh": 0.025,
      "last_seen_at": "2025-03-18T14:22:00"
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

**curl:**

```bash
curl "http://localhost:8000/api/v1/agents?status=running&risk_min=50&sort_by=current_risk_score&sort_order=desc" \
  -H "Authorization: Bearer <jwt>"
```

---

### GET /agents/{agent_id}

Get agent detail including the last 20 steps.

**Auth:** JWT

**Response (200):**

```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "external_id": "order-bot-session-42",
  "name": "order-bot-session-42",
  "status": "killed",
  "current_risk_score": 82.1,
  "total_cost": 0.52,
  "total_tokens": 18400,
  "total_steps": 12,
  "total_co2_grams": 7.24,
  "total_kwh": 0.037,
  "last_seen_at": "2025-03-18T14:25:00",
  "recent_steps": [
    {
      "step_number": 1,
      "input_preview": "Find cheapest flight from SFO to NRT...",
      "output_preview": "Searching across 3 flight providers...",
      "tokens_used": 250,
      "cost": 0.0075,
      "tool_name": "web_search",
      "error_message": null,
      "created_at": "2025-03-18T14:20:00"
    }
  ]
}
```

**Errors:**

| Status | Cause |
|--------|-------|
| 404 | Agent not found |
| 403 | Agent belongs to another organization |

---

## Incidents

### GET /incidents

List incidents across all projects with optional filters and pagination.

**Auth:** JWT

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| incident_type | string | null | Filter by type: `semantic_loop`, `diminishing_returns`, `context_bloat`, `error_cascade`, `cost_spike`, `composite` |
| agent_id | UUID | null | Filter by agent |
| date_from | datetime | null | ISO 8601 start date |
| date_to | datetime | null | ISO 8601 end date |
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page (1-100) |

**Response (200):**

```json
{
  "items": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "agent_id": "990e8400-e29b-41d4-a716-446655440000",
      "agent_name": "order-bot-session-42",
      "incident_type": "semantic_loop",
      "risk_score_at_kill": 82.1,
      "cost_avoided": 3.45,
      "co2_avoided_grams": 12.6,
      "steps_at_kill": 12,
      "created_at": "2025-03-18T14:25:00"
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20
}
```

**curl:**

```bash
curl "http://localhost:8000/api/v1/incidents?incident_type=semantic_loop&page=1" \
  -H "Authorization: Bearer <jwt>"
```

---

### GET /incidents/stats

Aggregated incident statistics by type.

**Auth:** JWT

**Response (200):**

```json
{
  "total_count": 47,
  "by_type": {
    "semantic_loop": 18,
    "error_cascade": 12,
    "diminishing_returns": 9,
    "cost_spike": 5,
    "context_bloat": 3
  },
  "total_cost_avoided": 142.87,
  "total_co2_avoided_grams": 523.4
}
```

**curl:**

```bash
curl http://localhost:8000/api/v1/incidents/stats \
  -H "Authorization: Bearer <jwt>"
```

---

### GET /incidents/{incident_id}

Get full incident detail with forensic snapshot.

**Auth:** JWT

**Response (200):**

```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "agent_id": "990e8400-e29b-41d4-a716-446655440000",
  "agent_name": "order-bot-session-42",
  "incident_type": "semantic_loop",
  "risk_score_at_kill": 82.1,
  "cost_avoided": 3.45,
  "co2_avoided_grams": 12.6,
  "steps_at_kill": 12,
  "created_at": "2025-03-18T14:25:00",
  "snapshot": {
    "risk_breakdown": {
      "similarity": 92.3,
      "diminishing_returns": 78.1,
      "context_inflation": 45.2,
      "error_cascade": 0.0,
      "cost_velocity": 38.7
    },
    "last_3_outputs": ["...", "...", "..."]
  },
  "kill_reason_detail": "Mean pairwise similarity 0.923 across 3 outputs. Agent producing near-identical responses."
}
```

---

### GET /incidents/{incident_id}/export

Export incident as a downloadable JSON file.

**Auth:** JWT

**Response (200):** JSON file download with `Content-Disposition: attachment` header.

```json
{
  "incident_id": "aa0e8400-...",
  "agent_id": "990e8400-...",
  "agent_name": "order-bot-session-42",
  "project_id": "770e8400-...",
  "incident_type": "semantic_loop",
  "risk_score_at_kill": 82.1,
  "cost_at_kill": 0.52,
  "cost_avoided": 3.45,
  "co2_avoided_grams": 12.6,
  "kwh_avoided": 0.032,
  "steps_at_kill": 12,
  "snapshot": { "..." : "..." },
  "kill_reason_detail": "...",
  "created_at": "2025-03-18T14:25:00"
}
```

**curl:**

```bash
curl -o incident.json http://localhost:8000/api/v1/incidents/aa0e.../export \
  -H "Authorization: Bearer <jwt>"
```

---

## Analytics

### GET /analytics/overview

KPI summary for the organization dashboard.

**Auth:** JWT

**Response (200):**

```json
{
  "total_savings": 142.87,
  "active_agents": 12,
  "incidents_today": 3,
  "avg_risk_score": 28.4
}
```

| Field | Description |
|-------|-------------|
| total_savings | Total cost avoided by all kills (USD) |
| active_agents | Number of agents with status `running` or `warning` |
| incidents_today | Incidents created in the last 24 hours |
| avg_risk_score | Mean risk score across all active agents |

**curl:**

```bash
curl http://localhost:8000/api/v1/analytics/overview \
  -H "Authorization: Bearer <jwt>"
```

---

### GET /analytics/savings-timeline

Daily cost savings for the last N days.

**Auth:** JWT

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| days | int | 30 | Number of days (1-365) |

**Response (200):**

```json
[
  { "date": "2025-03-18", "cost_saved": 12.45 },
  { "date": "2025-03-17", "cost_saved": 8.90 },
  { "date": "2025-03-16", "cost_saved": 15.22 }
]
```

---

### GET /analytics/top-agents

Top N agents ranked by total cost.

**Auth:** JWT

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 10 | Number of agents to return (1-50) |

**Response (200):**

```json
[
  { "agent_name": "order-bot-session-42", "total_cost": 12.45 },
  { "agent_name": "research-agent-7", "total_cost": 8.90 }
]
```

---

### GET /analytics/incident-distribution

Incident count by type with percentages.

**Auth:** JWT

**Response (200):**

```json
[
  { "type": "semantic_loop", "count": 18, "percentage": 38.3 },
  { "type": "error_cascade", "count": 12, "percentage": 25.5 },
  { "type": "diminishing_returns", "count": 9, "percentage": 19.1 },
  { "type": "cost_spike", "count": 5, "percentage": 10.6 },
  { "type": "context_bloat", "count": 3, "percentage": 6.4 }
]
```

---

### GET /analytics/carbon-report

Carbon impact report with equivalences and monthly trend.

**Auth:** JWT

**Response (200):**

```json
{
  "total_kwh_saved": 1.24,
  "total_co2_saved_kg": 0.48,
  "equivalences": {
    "kwh": 1.24,
    "co2_grams": 483.6,
    "equivalent_trees": 0.022,
    "equivalent_km_car": 4.03,
    "equivalent_phone_charges": 58.8
  },
  "monthly_trend": [
    { "month": "2025-03", "kwh": 0.85, "co2_kg": 0.33 },
    { "month": "2025-02", "kwh": 0.39, "co2_kg": 0.15 }
  ]
}
```

---

### GET /analytics/heatmap

7x24 activity matrix (day of week by hour of day). Used for the dashboard activity heatmap.

**Auth:** JWT

**Response (200):**

```json
{
  "data": [[0, 2, 5, 12, ...], ...],
  "labels_x": ["00", "01", "02", ..., "23"],
  "labels_y": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
}
```

`data` is a 7x24 matrix where `data[day][hour]` is the number of steps recorded during that time slot.

---

## Settings

All settings endpoints operate on a specific project. If `project_id` is not provided as a query parameter, the first project in the organization is used.

### GET /settings/detection

Return current detection thresholds.

**Auth:** JWT

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| project_id | UUID | null | Target project (defaults to first project) |

**Response (200):**

```json
{
  "kill_threshold": 75,
  "warn_threshold": 50,
  "similarity": 85,
  "diminishing_returns": 0.10,
  "context_inflation_growth": 0.20,
  "context_inflation_novelty": 0.15
}
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| kill_threshold | int | 1-100 | Composite score that triggers agent kill |
| warn_threshold | int | 1-100 | Composite score that triggers a warning |
| similarity | int | 1-100 | Cosine similarity percentage to flag semantic loop |
| diminishing_returns | float | 0-1 | Novelty ratio below which diminishing returns is flagged |
| context_inflation_growth | float | 0-5 | Context growth rate threshold |
| context_inflation_novelty | float | 0-1 | Output novelty below which context bloat is flagged |

---

### PUT /settings/detection

Update detection thresholds. `warn_threshold` must be less than `kill_threshold`.

**Auth:** JWT

**Request:**

```json
{
  "kill_threshold": 80,
  "warn_threshold": 55,
  "similarity": 90,
  "diminishing_returns": 0.08,
  "context_inflation_growth": 0.25,
  "context_inflation_novelty": 0.12
}
```

**Response (200):** Updated thresholds object.

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | `warn_threshold >= kill_threshold` |
| 422 | Value out of range |

**curl:**

```bash
curl -X PUT http://localhost:8000/api/v1/settings/detection \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"kill_threshold":80,"warn_threshold":55,"similarity":90,"diminishing_returns":0.08,"context_inflation_growth":0.25,"context_inflation_novelty":0.12}'
```

---

### GET /settings/budget

Return project budget limits.

**Auth:** JWT

**Response (200):**

```json
{
  "budget_limit": 500.0,
  "max_cost_per_agent": 10.0,
  "max_steps_per_agent": 100
}
```

All fields are nullable. `null` means no limit is enforced.

---

### PUT /settings/budget

Update budget limits.

**Auth:** JWT

**Request:**

```json
{
  "budget_limit": 1000.0,
  "max_cost_per_agent": 25.0,
  "max_steps_per_agent": 200
}
```

**Response (200):** Updated budget object.

---

### GET /settings/notifications

Return notification configuration.

**Auth:** JWT

**Response (200):**

```json
{
  "email_on_kill": true,
  "email_on_warn": false,
  "slack_webhook": null,
  "slack_on_kill": true,
  "slack_on_warn": false
}
```

---

### PUT /settings/notifications

Update notification configuration.

**Auth:** JWT

**Request:**

```json
{
  "email_on_kill": true,
  "email_on_warn": true,
  "slack_webhook": "https://hooks.slack.com/services/T00/B00/xxx",
  "slack_on_kill": true,
  "slack_on_warn": true
}
```

**Response (200):** Updated notification settings.

---

## Playground

### GET /playground/scenarios

Return available simulation scenarios.

**Auth:** JWT

**Response (200):**

```json
[
  {
    "id": "semantic_loop",
    "name": "Semantic Loop",
    "description": "Agent repeatedly generates near-identical outputs while searching for flights.",
    "expected_kill_step": 8,
    "primary_detector": "similarity"
  },
  {
    "id": "cost_explosion",
    "name": "Cost Explosion",
    "description": "Agent switches to expensive model mid-session, cost velocity spikes.",
    "expected_kill_step": 12,
    "primary_detector": "cost_velocity"
  },
  {
    "id": "error_cascade",
    "name": "Error Cascade",
    "description": "Agent retries a broken API tool indefinitely with the same error.",
    "expected_kill_step": 6,
    "primary_detector": "error_cascade"
  }
]
```

**curl:**

```bash
curl http://localhost:8000/api/v1/playground/scenarios \
  -H "Authorization: Bearer <jwt>"
```

---

### POST /playground/simulate

Start a simulation scenario. Results are streamed via WebSocket.

**Auth:** JWT

**Request:**

```json
{
  "scenario": "semantic_loop"
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| scenario | string | yes | `semantic_loop`, `cost_explosion`, `error_cascade` |

**Response (200):**

```json
{
  "session_id": "a1b2c3d4e5f6",
  "scenario": "semantic_loop",
  "message": "Simulation started. Connect to /ws/playground/a1b2c3d4e5f6 for live results."
}
```

After receiving the `session_id`, connect to the WebSocket endpoint to receive real-time step results.

**curl:**

```bash
curl -X POST http://localhost:8000/api/v1/playground/simulate \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"semantic_loop"}'
```

---

## WebSocket

### WS /ws/events

Live event stream for the dashboard. Publishes step and incident events for all projects in the organization.

**Auth:** JWT (passed as query parameter `token`)

**Connection:**

```
ws://localhost:8000/api/v1/ws/events?token=<jwt>
```

**Event format:**

```json
{
  "type": "step",
  "data": {
    "agent_id": "990e8400-...",
    "agent_name": "order-bot-session-42",
    "step_number": 7,
    "risk_score": 62.4,
    "action": "warn",
    "cost": 0.0075,
    "timestamp": "2025-03-18T14:22:00"
  }
}
```

```json
{
  "type": "incident",
  "data": {
    "incident_id": "aa0e8400-...",
    "agent_name": "order-bot-session-42",
    "incident_type": "semantic_loop",
    "risk_score": 82.1,
    "cost_avoided": 3.45,
    "timestamp": "2025-03-18T14:25:00"
  }
}
```

### WS /ws/playground/{session_id}

Live stream for a playground simulation session.

**Connection:**

```
ws://localhost:8000/api/v1/ws/playground/a1b2c3d4e5f6
```

Publishes one event per simulated step with full risk analysis results, followed by a final `complete` event.

---

## Rate Limiting

All endpoints are rate-limited to **100 requests per minute** per API key or IP address. When the limit is exceeded:

**Response (429):**

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

Headers:

```
Retry-After: 60
```

Health checks (`/health`), OpenAPI docs (`/docs`, `/openapi.json`), and WebSocket connections are exempt from rate limiting.
