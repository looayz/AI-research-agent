#!/usr/bin/env bash
set -e

echo "Starting AI Research Agent..."

if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv .venv
fi

echo "[2/3] Installing dependencies..."
source .venv/bin/activate
pip install -q -r apps/api/requirements.txt
(cd apps/web && npm install --silent)

echo "[3/3] Starting services..."
(cd apps/api && uvicorn app.main:app --port 8000 --reload) &
API_PID=$!

(cd apps/web && npm run dev) &
WEB_PID=$!

echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/docs"

trap "kill $API_PID $WEB_PID" EXIT
wait
