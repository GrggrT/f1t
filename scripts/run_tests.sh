#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

CLEANUP=false
PYTEST_ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--cleanup" ]]; then
    CLEANUP=true
  else
    PYTEST_ARGS+=("$arg")
  fi
done

docker compose -f docker-compose.test.yml up -d postgres-test
docker compose -f docker-compose.test.yml run --rm --build backend-test "${PYTEST_ARGS[@]}"

if [[ "$CLEANUP" == "true" ]]; then
  docker compose -f docker-compose.test.yml down -v
fi
