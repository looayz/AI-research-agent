@echo off
echo Starting AI Research Agent...

if not exist ".venv" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
)

echo [2/3] Checking dependencies...
call .\.venv\Scripts\activate.bat
pip install -q -r apps/api/requirements.txt

echo [3/3] Launching Backend on port 8000 and Frontend on port 3000...
start "AI Research Backend (FastAPI)" cmd /k ".\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --port 8000 --reload"
start "AI Research Frontend (Next.js)" cmd /k "cd apps/web && npm run dev"

echo Services started!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000/docs
