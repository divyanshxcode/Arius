#!/usr/bin/env bash
# Create venv (once), install deps, run the broker on :8000
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  echo "creating venv (python 3.12)…"
  py -3.12 -m venv .venv
  ./.venv/Scripts/python.exe -m pip install --upgrade pip -q
  ./.venv/Scripts/python.exe -m pip install -r requirements.txt -q
fi

exec ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
