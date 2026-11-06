#!/usr/bin/env bash
# Start an image the way production does, without secrets, and wait until it reports healthy.
# Catches images that are broken on their own: missing files, crashes at start, failed migrations.
#
#   smoke.sh <backend|parser> <image>
set -euo pipefail

app=${1:?usage: smoke.sh <backend|parser> <image>}
image=${2:?usage: smoke.sh <backend|parser> <image>}
network=finchie-smoke

cleanup() {
  local status=$?
  if [ "$status" -ne 0 ] && docker inspect smoke >/dev/null 2>&1; then
    echo "--- smoke container logs"
    docker logs smoke 2>&1 | tail -50 || true
  fi
  docker rm -f smoke smoke-postgres >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

# wait_for <description> <command...>: retry for about a minute.
wait_for() {
  local what=$1
  shift
  for _ in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then
      echo "$app: $what"
      return 0
    fi
    sleep 2
  done
  echo "::error::$app: timed out waiting until $what"
  return 1
}

docker network create "$network" >/dev/null

case "$app" in
  parser)
    docker run -d --name smoke --network "$network" "$image" >/dev/null
    wait_for "gRPC health reports SERVING" docker exec smoke python -m finchie_parser.healthcheck
    ;;
  backend)
    # The backend applies migrations at startup and /healthz pings the database, so it needs a real one.
    docker run -d --name smoke-postgres --network "$network" \
      -e POSTGRES_USER=finchie -e POSTGRES_PASSWORD=finchie -e POSTGRES_DB=finchie \
      postgres:18.6 >/dev/null
    # Over TCP: during initdb the server only listens on its Unix socket.
    wait_for "postgres accepts TCP connections" docker exec smoke-postgres pg_isready -h 127.0.0.1 -U finchie
    docker run -d --name smoke --network "$network" -p 127.0.0.1:8080:8080 \
      -e "BACKEND_DATABASE_URL=postgres://finchie:finchie@smoke-postgres:5432/finchie?sslmode=disable" \
      -e BACKEND_PARSER_ADDR=parser:50051 \
      "$image" >/dev/null
    wait_for "/healthz answers ok" curl -fsS http://127.0.0.1:8080/healthz
    # Any app route gets the embedded web app's shell, which loads its scripts from /_app/.
    if ! curl -fsS http://127.0.0.1:8080/statements | grep -q '/_app/immutable/'; then
      echo "::error::backend: the web app is not embedded (no /_app/ scripts in the page)"
      exit 1
    fi
    echo "backend: serves the web app"
    ;;
  *)
    echo "unknown app: $app (expected backend or parser)" >&2
    exit 2
    ;;
esac
