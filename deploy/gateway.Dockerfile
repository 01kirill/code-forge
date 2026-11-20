FROM node:20.20.2-bookworm-slim AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --fetch-retries=1 --fetch-timeout=15000
COPY frontend .
RUN npm run build

FROM nginx:1.28-bookworm
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
