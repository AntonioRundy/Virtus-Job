FROM node:22-alpine AS base

# ─── Development ──────────────────────────────────────────────────────────────
# Build context: workspace root (.)
FROM base AS development
WORKDIR /workspace

# Copy package descriptors first for layer caching
COPY apps/web/package*.json ./apps/web/

# Install web deps (packages/types and packages/api-client are TypeScript source,
# not npm packages, so no workspace install needed here)
RUN cd apps/web && npm install

# Copy sources (overridden by volume mounts in dev mode)
COPY packages/ ./packages/
COPY apps/web/ ./apps/web/

WORKDIR /workspace/apps/web
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ─── Builder ──────────────────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /workspace

COPY apps/web/package*.json ./apps/web/
RUN cd apps/web && npm ci

COPY packages/ ./packages/
COPY apps/web/ ./apps/web/

WORKDIR /workspace/apps/web
RUN npm run build

# ─── Production ───────────────────────────────────────────────────────────────
FROM base AS production
ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /workspace/apps/web/.next/standalone ./
COPY --from=builder /workspace/apps/web/.next/static ./.next/static
COPY --from=builder /workspace/apps/web/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
