# syntax=docker/dockerfile:1

# Stage 1: build Angular SPA
FROM node:20-alpine AS builder
WORKDIR /app

# Instalar dependencias con lockfile (reproducible)
COPY package.json package-lock.json ./
RUN npm ci

# Copiar el resto del código del frontend y buildear
COPY . .
RUN npm run build -- --configuration=production

# ─────────────────────────────────────────────────────────
# Stage 2: nginx sirviendo el SPA
FROM nginx:1.27-alpine

# Default port (Railway sobreescribe via $PORT en runtime)
ENV PORT=8080

# El builder de Angular 17+ genera dist/<name>/browser/
COPY --from=builder /app/dist/crm-frontend/browser /usr/share/nginx/html

# nginx:alpine corre envsubst sobre /etc/nginx/templates/*.template al arrancar,
# reemplazando ${PORT} con la variable del entorno y volcando a /etc/nginx/conf.d/.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080

# Healthcheck local (Railway usa probes HTTP propios, esto es para docker run manual)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:${PORT}/healthz || exit 1
