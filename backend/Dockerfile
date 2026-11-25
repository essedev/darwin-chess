# One image for both long-lived services: `core` (orchestrator + referee, drives pi and
# Docker) and `api` (read-only dashboard API, serves the built frontend).
# Build context: the repository root.

FROM node:24-bookworm-slim AS node
RUN corepack enable
WORKDIR /build/agent
COPY agent/package.json agent/pnpm-lock.yaml agent/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --prod
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
COPY frontend/pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM docker:29-cli AS docker-cli

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY seed/ /app/seed/
COPY agent/darwin-extension.ts /app/agent/
COPY --from=node /build/agent/node_modules /app/agent/node_modules
COPY --from=node /build/frontend/dist /app/frontend/dist
ENV PATH=/app/backend/.venv/bin:$PATH DARWIN_AGENT_DIR=/app/agent DARWIN_FRONTEND_DIST=/app/frontend/dist
CMD ["python", "-m", "darwin.orchestrator"]
