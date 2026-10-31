#!/usr/bin/env bash
# Install (once) and run the Vite dashboard on :5173
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  echo "installing frontend deps…"
  npm install --no-fund --no-audit
fi

exec npm run dev
