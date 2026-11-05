# syntax=docker/dockerfile:1
# The backend embeds the web app, so this builds from the repository root:
#   docker build -f services/backend/Dockerfile .
# Dockerfile.dockerignore next to this file limits the context to web/ and services/backend/.

FROM node:26-alpine AS web
WORKDIR /src
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
# The pnpm version is pinned once, in package.json's packageManager field.
RUN npm install --global "pnpm@$(node -p "require('./package.json').packageManager.split('@')[1]")"
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build


FROM golang:1.27 AS build
WORKDIR /src
COPY services/backend/go.mod services/backend/go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY services/backend/ ./
COPY --from=web /src/build ./internal/web/dist
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/backend ./cmd/backend


FROM gcr.io/distroless/static-debian12
COPY --from=build /out/backend /backend
USER 1654:1654
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD ["/backend", "healthcheck"]
ENTRYPOINT ["/backend"]
