#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DUMP=${1:?"Usage: $0 <dump-file.pgc>"}

if [ ! -f "$DUMP" ]; then
  echo "ERROR: $DUMP not found" >&2
  exit 1
fi

if [ -f .env ]; then
  set -a; source .env; set +a
fi

POSTGRES_USER=${POSTGRES_USER:-f1league}
POSTGRES_DB=${POSTGRES_DB:-f1league}

cat <<EOF
======================================================================
WARNING: Restore will OVERWRITE the current database.
   Dump: $DUMP
   DB:   $POSTGRES_DB (user: $POSTGRES_USER)

Backend and bot will be stopped during restore.
======================================================================
EOF
read -r -p "Continue? Type 'yes' to proceed: " confirm
if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

echo "Stopping backend and bot..."
docker compose stop backend bot

echo "Restoring from $DUMP..."
docker compose exec -T postgres pg_restore \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner \
  < "$DUMP"

echo "Starting backend and bot..."
docker compose start backend bot

echo "Done. Verify the application is working."
