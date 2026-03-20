# AgentBreaker -- Google Cloud Deployment

## Architecture

```
                  Cloud Run (frontend)        Cloud Run (backend)
User  ───>  nginx serving SPA (256Mi)  ───>  FastAPI + Uvicorn (2Gi)
                                                  │           │
                                          Cloud SQL (PG16)  Memorystore Redis
                                          db-f1-micro        1GB Basic
```

## Prerequisites

1. **Google Cloud account** with billing enabled
2. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```
3. A GCP project (the script will create resources inside it)

## One-Command Deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh YOUR_PROJECT_ID
```

Optional second argument for region (defaults to `europe-west1`):

```bash
./deploy/deploy.sh YOUR_PROJECT_ID us-central1
```

The script will:
- Enable all required APIs
- Create Artifact Registry, Cloud SQL, Memorystore Redis, VPC connector
- Build and push Docker images via Cloud Build
- Deploy backend and frontend to Cloud Run
- Run database migrations
- Print the live URLs

First deploy takes 15-25 minutes (Cloud SQL and Redis provisioning). Subsequent deploys take 3-5 minutes.

## Custom Domain

1. Go to Cloud Run in the Console
2. Select `agentbreaker-web` (frontend) or `agentbreaker-api` (backend)
3. Click "Manage Custom Domains" > "Add Mapping"
4. Follow the DNS verification steps

For a single domain with path-based routing, use a Cloud Load Balancer instead:
- `yourdomain.com/*` -> frontend
- `yourdomain.com/api/*` -> backend

## Redeploying After Code Changes

For quick redeploys (no infrastructure changes):

```bash
# Backend only
gcloud builds submit backend/ \
  --tag europe-west1-docker.pkg.dev/YOUR_PROJECT/agentbreaker/backend:latest
gcloud run deploy agentbreaker-api \
  --image europe-west1-docker.pkg.dev/YOUR_PROJECT/agentbreaker/backend:latest \
  --region europe-west1

# Frontend only
gcloud builds submit frontend/ \
  --tag europe-west1-docker.pkg.dev/YOUR_PROJECT/agentbreaker/frontend:latest
gcloud run deploy agentbreaker-web \
  --image europe-west1-docker.pkg.dev/YOUR_PROJECT/agentbreaker/frontend:latest \
  --region europe-west1
```

Or use Cloud Build with the provided config:

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml .
```

## CI/CD with Cloud Build Trigger

```bash
gcloud builds triggers create github \
  --repo-name=agentbreaker \
  --repo-owner=YOUR_GITHUB_USER \
  --branch-pattern="^main$" \
  --build-config=deploy/cloudbuild.yaml
```

## Estimated Monthly Costs

| Resource | Spec | Estimated Cost |
|----------|------|---------------|
| Cloud Run (backend) | 2 vCPU, 2Gi, scale-to-zero | $0-15 (pay per request) |
| Cloud Run (frontend) | 1 vCPU, 256Mi, scale-to-zero | $0-5 (mostly free tier) |
| Cloud SQL (PostgreSQL) | db-f1-micro, 10GB | $8-10 |
| Memorystore Redis | 1GB Basic | $35 |
| Artifact Registry | Storage | $1-2 |
| Cloud Build | Build minutes | $0-3 |
| **Total** | | **$20-35/month** |

To reduce costs:
- Memorystore Redis is the largest fixed cost. For low-traffic, you can skip it and use in-memory caching instead (remove Redis from deploy.sh and unset REDIS_URL).
- Cloud SQL db-f1-micro is the smallest tier. Consider stopping the instance when not in use.
- Cloud Run scales to zero by default, so idle costs are minimal.

## Monitoring

```bash
# View backend logs
gcloud run services logs read agentbreaker-api --region=europe-west1 --limit=50

# View frontend logs
gcloud run services logs read agentbreaker-web --region=europe-west1 --limit=50

# Check service status
gcloud run services describe agentbreaker-api --region=europe-west1
gcloud run services describe agentbreaker-web --region=europe-west1
```

## Tearing Down

To remove all resources and stop billing:

```bash
PROJECT_ID=YOUR_PROJECT_ID
REGION=europe-west1

gcloud run services delete agentbreaker-api --region=$REGION --quiet
gcloud run services delete agentbreaker-web --region=$REGION --quiet
gcloud run jobs delete agentbreaker-migrate --region=$REGION --quiet
gcloud sql instances delete agentbreaker-db --quiet
gcloud redis instances delete agentbreaker-cache --region=$REGION --quiet
gcloud compute networks vpc-access connectors delete agentbreaker-vpc --region=$REGION --quiet
gcloud artifacts repositories delete agentbreaker --location=$REGION --quiet
gcloud secrets delete agentbreaker-db-password --quiet
gcloud secrets delete agentbreaker-secret-key --quiet
```

## Environment Variables Reference

### Backend (Cloud Run)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Set by deploy script |
| `REDIS_URL` | Redis connection string | Set by deploy script |
| `SECRET_KEY` | JWT signing key | Auto-generated |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["*"]` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `1440` |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | `100` |
| `DEFAULT_KILL_THRESHOLD` | Default kill threshold | `75` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |
| `ENVIRONMENT` | Runtime environment | `production` |
