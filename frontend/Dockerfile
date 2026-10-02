# frontend/Dockerfile
# Build context = repo root: `docker build -f frontend/Dockerfile .`

# ---------- Stage 1: build ----------
FROM node:20-alpine AS build

WORKDIR /app

# Copy manifests first for layer caching.
COPY frontend/package.json frontend/package-lock.json* ./

# Use npm ci when a lockfile is present (reproducible), else fall back to install.
RUN if [ -f package-lock.json ]; then npm ci; else echo "WARN: no package-lock.json — falling back to npm install"; npm install; fi

# Copy source and build.
COPY frontend/ ./

# Optional: bake the API base URL at build time.
# If your client.ts reads import.meta.env.VITE_API_BASE_URL, pass this via --build-arg.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---------- Stage 2: serve ----------
FROM nginx:alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]