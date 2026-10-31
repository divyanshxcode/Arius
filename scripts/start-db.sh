#!/usr/bin/env bash
# Start the database containers.
#   scripts/start-db.sh          -> 3-node Yugabyte + Tiger Data
#   scripts/start-db.sh lite     -> single-node Yugabyte + Tiger Data (low RAM)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop (WSL2 engine) or run the backend"
  echo "with DB_MODE=auto and let it use the SQLite dev fallback."
  exit 1
fi

MODE="${1:-full}"
if [ "$MODE" = "lite" ]; then
  docker compose -f docker-compose.lite.yml up -d
else
  docker compose up -d
fi

echo "waiting for Yugabyte to accept SQL connections on 5433…"
for i in $(seq 1 60); do
  if docker compose ${MODE:+exec -T yb-node1 true} >/dev/null 2>&1; then :; fi
  if (timeout 2 bash -c "</dev/tcp/127.0.0.1/5433" 2>/dev/null); then
    echo "yugabyte: open"
    break
  fi
  sleep 2
done

echo "containers:"
docker compose ps 2>/dev/null || docker compose -f docker-compose.lite.yml ps
