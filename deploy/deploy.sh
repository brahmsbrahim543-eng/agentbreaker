#!/bin/bash
# AgentBreaker — Deploy to Google Cloud
# Prerequisites: gcloud CLI installed and authenticated, billing enabled
# Usage: ./deploy/deploy.sh [PROJECT_ID] [REGION]

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
PROJECT_ID="${1:-agentbreaker}"
REGION="${2:-europe-west1}"
SERVICE_NAME="agentbreaker"
DB_INSTANCE="${SERVICE_NAME}-db"
DB_NAME="${SERVICE_NAME}"
DB_USER="${SERVICE_NAME}"
REDIS_INSTANCE="${SERVICE_NAME}-cache"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}"
BACKEND_IMAGE="${REGISTRY}/backend:latest"
FRONTEND_IMAGE="${REGISTRY}/frontend:latest"

# Generate a random password if deploying for the first time
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 24 | tr -d '=/+' | head -c 32)}"

# ── Colors ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ── Preflight checks ──────────────────────────────────────────────────────────
if ! command -v gcloud &>/dev/null; then
    err "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo ""
echo "============================================"
echo "  AgentBreaker — Google Cloud Deployment"
echo "============================================"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "============================================"
echo ""

# Confirm project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
if [ "${CURRENT_PROJECT}" != "${PROJECT_ID}" ]; then
    log "Setting active project to ${PROJECT_ID}..."
    gcloud config set project "${PROJECT_ID}"
fi

# ── Step 1: Enable required APIs ──────────────────────────────────────────────
log "Enabling required Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    vpcaccess.googleapis.com \
    --project="${PROJECT_ID}"
ok "APIs enabled"

# ── Step 2: Create Artifact Registry repository ──────────────────────────────
log "Creating Artifact Registry repository..."
gcloud artifacts repositories create "${SERVICE_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="AgentBreaker container images" \
    --project="${PROJECT_ID}" 2>/dev/null || ok "Repository already exists"
ok "Artifact Registry ready"

# ── Step 3: Create Cloud SQL PostgreSQL instance ─────────────────────────────
log "Creating Cloud SQL PostgreSQL instance (this may take 5-10 minutes)..."
if gcloud sql instances describe "${DB_INSTANCE}" --project="${PROJECT_ID}" &>/dev/null; then
    ok "Cloud SQL instance already exists"
else
    gcloud sql instances create "${DB_INSTANCE}" \
        --database-version=POSTGRES_16 \
        --tier=db-f1-micro \
        --region="${REGION}" \
        --storage-auto-increase \
        --storage-size=10 \
        --backup-start-time=03:00 \
        --availability-type=zonal \
        --project="${PROJECT_ID}"
    ok "Cloud SQL instance created"
fi

# ── Step 4: Create database and user ─────────────────────────────────────────
log "Setting up database and user..."
gcloud sql databases create "${DB_NAME}" \
    --instance="${DB_INSTANCE}" \
    --project="${PROJECT_ID}" 2>/dev/null || ok "Database already exists"

gcloud sql users create "${DB_USER}" \
    --instance="${DB_INSTANCE}" \
    --password="${DB_PASSWORD}" \
    --project="${PROJECT_ID}" 2>/dev/null || warn "User already exists — password NOT updated"
ok "Database configured"

# ── Step 5: Create Memorystore Redis instance ────────────────────────────────
log "Creating Memorystore Redis instance (this may take 5-10 minutes)..."
if gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    ok "Redis instance already exists"
else
    gcloud redis instances create "${REDIS_INSTANCE}" \
        --size=1 \
        --region="${REGION}" \
        --redis-version=redis_7_0 \
        --project="${PROJECT_ID}"
    ok "Redis instance created"
fi

# Get Redis host IP
REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
    --region="${REGION}" \
    --format='value(host)' \
    --project="${PROJECT_ID}" 2>/dev/null || echo "")

REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
    --region="${REGION}" \
    --format='value(port)' \
    --project="${PROJECT_ID}" 2>/dev/null || echo "6379")

# ── Step 6: Create VPC Connector (needed for Redis access) ──────────────────
log "Creating Serverless VPC connector..."
gcloud compute networks vpc-access connectors create "${SERVICE_NAME}-vpc" \
    --region="${REGION}" \
    --range="10.8.0.0/28" \
    --project="${PROJECT_ID}" 2>/dev/null || ok "VPC connector already exists"
ok "VPC connector ready"

# ── Step 7: Store secrets ────────────────────────────────────────────────────
log "Storing secrets in Secret Manager..."
SECRET_KEY=$(openssl rand -base64 48 | tr -d '=/+' | head -c 64)

create_or_update_secret() {
    local name="$1" value="$2"
    if gcloud secrets describe "${name}" --project="${PROJECT_ID}" &>/dev/null; then
        echo -n "${value}" | gcloud secrets versions add "${name}" --data-file=- --project="${PROJECT_ID}" >/dev/null
    else
        echo -n "${value}" | gcloud secrets create "${name}" --data-file=- --replication-policy=automatic --project="${PROJECT_ID}" >/dev/null
    fi
}

create_or_update_secret "agentbreaker-db-password" "${DB_PASSWORD}"
create_or_update_secret "agentbreaker-secret-key" "${SECRET_KEY}"
ok "Secrets stored"

# Grant Cloud Run service account access to secrets
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding "agentbreaker-db-password" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" >/dev/null 2>&1 || true

gcloud secrets add-iam-policy-binding "agentbreaker-secret-key" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" >/dev/null 2>&1 || true

# ── Step 8: Build and push backend image ─────────────────────────────────────
log "Building backend Docker image..."
gcloud builds submit backend/ \
    --tag "${BACKEND_IMAGE}" \
    --project="${PROJECT_ID}" \
    --quiet
ok "Backend image pushed to ${BACKEND_IMAGE}"

# ── Step 9: Build and push frontend image ────────────────────────────────────
log "Building frontend Docker image..."
gcloud builds submit frontend/ \
    --tag "${FRONTEND_IMAGE}" \
    --project="${PROJECT_ID}" \
    --quiet
ok "Frontend image pushed to ${FRONTEND_IMAGE}"

# ── Step 10: Deploy backend to Cloud Run ─────────────────────────────────────
log "Deploying backend to Cloud Run..."
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${SQL_CONNECTION}"

REDIS_URL=""
if [ -n "${REDIS_HOST}" ]; then
    REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
fi

gcloud run deploy agentbreaker-api \
    --image="${BACKEND_IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=0 \
    --max-instances=10 \
    --concurrency=80 \
    --timeout=300 \
    --set-env-vars="^||^DATABASE_URL=${DATABASE_URL}||REDIS_URL=${REDIS_URL}||SECRET_KEY=${SECRET_KEY}||ENVIRONMENT=production||CORS_ORIGINS=[\"*\"]||ACCESS_TOKEN_EXPIRE_MINUTES=1440||RATE_LIMIT_PER_MINUTE=100||DEFAULT_KILL_THRESHOLD=75||EMBEDDING_MODEL=all-MiniLM-L6-v2" \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --vpc-connector="${SERVICE_NAME}-vpc" \
    --project="${PROJECT_ID}"
ok "Backend deployed"

# ── Step 11: Get backend URL and deploy frontend ────────────────────────────
BACKEND_URL=$(gcloud run services describe agentbreaker-api \
    --region="${REGION}" \
    --format='value(status.url)' \
    --project="${PROJECT_ID}")

log "Deploying frontend to Cloud Run..."
gcloud run deploy agentbreaker-web \
    --image="${FRONTEND_IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --memory=256Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=5 \
    --concurrency=200 \
    --timeout=60 \
    --set-env-vars="BACKEND_URL=${BACKEND_URL}" \
    --project="${PROJECT_ID}"
ok "Frontend deployed"

# ── Step 12: Run database migrations ────────────────────────────────────────
log "Running database migrations..."
gcloud run jobs create agentbreaker-migrate \
    --image="${BACKEND_IMAGE}" \
    --region="${REGION}" \
    --set-env-vars="DATABASE_URL=${DATABASE_URL}" \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --vpc-connector="${SERVICE_NAME}-vpc" \
    --command="alembic" \
    --args="upgrade,head" \
    --project="${PROJECT_ID}" 2>/dev/null || \
gcloud run jobs update agentbreaker-migrate \
    --image="${BACKEND_IMAGE}" \
    --region="${REGION}" \
    --set-env-vars="DATABASE_URL=${DATABASE_URL}" \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --vpc-connector="${SERVICE_NAME}-vpc" \
    --command="alembic" \
    --args="upgrade,head" \
    --project="${PROJECT_ID}"

gcloud run jobs execute agentbreaker-migrate \
    --region="${REGION}" \
    --wait \
    --project="${PROJECT_ID}" || warn "Migration job may have already run"

# ── Step 13: Print results ──────────────────────────────────────────────────
FRONTEND_URL=$(gcloud run services describe agentbreaker-web \
    --region="${REGION}" \
    --format='value(status.url)' \
    --project="${PROJECT_ID}")

echo ""
echo "============================================"
echo -e "  ${GREEN}AgentBreaker deployed successfully!${NC}"
echo "============================================"
echo ""
echo "  Dashboard:  ${FRONTEND_URL}"
echo "  API:        ${BACKEND_URL}"
echo "  API docs:   ${BACKEND_URL}/docs"
echo ""
echo "  Cloud SQL:  ${DB_INSTANCE} (${REGION})"
echo "  Redis:      ${REDIS_INSTANCE} (${REDIS_HOST}:${REDIS_PORT})"
echo ""
echo "============================================"
echo ""
echo "  Next steps:"
echo "  1. Update CORS_ORIGINS to restrict to your domain"
echo "  2. Set up a custom domain (see deploy/README.md)"
echo "  3. Update the frontend BACKEND_URL env var"
echo "     to point to your API domain"
echo ""
echo "  Database password stored in Secret Manager:"
echo "  gcloud secrets versions access latest --secret=agentbreaker-db-password"
echo ""
echo "============================================"
