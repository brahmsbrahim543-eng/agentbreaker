# AgentBreaker Frontend — Production Dockerfile
# Multi-stage: build with Node, serve with nginx

# ── Stage 1: Build ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source and build
COPY . .
ARG VITE_API_URL=https://agentbreaker-api.onrender.com
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Stage 2: Serve ─────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# nginx on Cloud Run must listen on 8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO /dev/null http://localhost:8080/health || exit 1

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
