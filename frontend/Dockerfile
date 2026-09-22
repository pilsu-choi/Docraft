# Build context: repo root (docker compose sets `context: .`).
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# nginx-unprivileged: non-root (uid 101) by default and listens on 8080, so k8s can run the
# pod with runAsNonRoot + all capabilities dropped without CHOWN/SETUID/SETGID/NET_BIND_SERVICE.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
