#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

export COMPOSE_PROJECT_NAME=f1t-staging

docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.override.yml \
  down -v

echo "Staging torn down, volume deleted"
