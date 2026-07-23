FROM node:22-alpine AS build

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

ARG APP_VERSION=development
ENV APP_VERSION=$APP_VERSION
RUN case "$APP_VERSION" in development) ;; *[!0-9a-f]*|'') exit 1 ;; *) test "${#APP_VERSION}" -eq 40 ;; esac
RUN printf '{"version":"%s"}\n' "$APP_VERSION" > /app/out/version.json

FROM nginx:1.30.4-alpine@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46

COPY --from=build /app/out /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1
