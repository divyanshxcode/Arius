#!/usr/bin/env bash
# Arius environment check — run before the hackathon.
set -u
echo "=== Arius environment ==="
echo -n "python (py -3.12): "; py -3.12 --version 2>/dev/null || echo "MISSING"
echo -n "node:              "; node --version 2>/dev/null || echo "MISSING"
echo -n "npm:               "; npm --version 2>/dev/null || echo "MISSING"
echo -n "git:               "; git --version 2>/dev/null || echo "MISSING"

if command -v docker >/dev/null 2>&1; then
  echo -n "docker:            "; docker --version
  echo -n "compose:           "; docker compose version | head -1
  echo -n "daemon:            "; docker info >/dev/null 2>&1 && echo "running" || echo "NOT RUNNING (start Docker Desktop)"
else
  echo "docker:            NOT INSTALLED  -> SQLite dev fallback will be used"
  echo "                   install Docker Desktop, enable WSL2 engine:"
  echo "                   https://docs.docker.com/desktop/setup/install/windows-install/"
fi

echo
echo -n "port 8000: "; (curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://localhost:8000/health || true) ; echo " (broker)"
echo -n "port 5433: "; (timeout 2 bash -c "</dev/tcp/127.0.0.1/5433" 2>/dev/null && echo open || echo closed) ; echo " (yugabyte)"
echo -n "port 5432: "; (timeout 2 bash -c "</dev/tcp/127.0.0.1/5432" 2>/dev/null && echo open || echo closed) ; echo " (tiger)"
