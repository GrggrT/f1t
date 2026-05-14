#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DUMP=${1:?"Usage: $0 <production-dump.pgc>"}

if [ ! -f "$DUMP" ]; then
  echo "ERROR: dump file not found: $DUMP" >&2
  exit 1
fi

if [ -f .env ]; then
  set -a; source .env; set +a
fi

export COMPOSE_PROJECT_NAME=f1t-staging

docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.override.yml \
  up -d postgres

echo "Waiting for staging postgres to become ready..."
until docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.override.yml \
  exec -T postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
  sleep 1
done

echo "Restoring dump: $DUMP"
docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.override.yml \
  exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner \
  < "$DUMP"

docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.override.yml \
  up -d backend

echo ""
echo "Staging up:"
echo "  backend  = http://localhost:8002"
echo "  postgres = localhost:5433"
echo ""
echo "Tear down: ./scripts/staging_down.sh"
