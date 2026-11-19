# =====================================================================
# DocuFlow AI - Frontend image (React + Vite -> static files on Nginx)
#
# Build:  docker build -t docuflow-frontend ./frontend
# Run:    docker run -p 8080:80 docuflow-frontend
#
# Two stages:
#   1. node   - installs dependencies and runs `vite build` (dist/)
#   2. nginx  - serves the static dist/ and proxies /api to the backend
# =====================================================================

# ---------- Stage 1: build the React app ----------
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies first (cached layer: only re-runs when the
# package files change)
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# Copy the source code and build for production
COPY . .
RUN npm run build

# ---------- Stage 2: serve with Nginx ----------
FROM nginx:1.27-alpine AS runtime

# Replace the default site with our SPA + API proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static build output from stage 1
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ > /dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
