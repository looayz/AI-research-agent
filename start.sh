#!/usr/bin/env bash
# One-command local start (macOS / Linux): API on :8000, web app on :3000.
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "Python 3.11+ is required: https://www.python.org/downloads/"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Python 3.11+ is required (found $(python3 -V))."; exit 1; }
command -v npm >/dev/null || { echo "Node.js 20.9+ is required: https://nodejs.org/"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (demo mode: no API key needed)."
fi

echo "[1/3] Python environment..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r apps/api/requirements.txt

echo "[2/3] Web dependencies..."
(cd apps/web && npm install --no-audit --no-fund --silent)

echo "[3/3] Starting services (Ctrl+C to stop)..."
trap 'trap - EXIT INT TERM; kill 0' EXIT INT TERM
(cd apps/api && ../../.venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app) &
(cd apps/web && npm run dev) &

echo
echo "  Web app : http://localhost:3000"
echo "  API docs: http://localhost:8000/api/docs"
echo
wait
