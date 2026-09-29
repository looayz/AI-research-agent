@echo off
rem One-command local start (Windows): API on :8000, web app on :3000.
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python 3.11+ is required: https://www.python.org/downloads/ & exit /b 1)
python -c "import sys; sys.exit(sys.version_info < (3, 11))" || (echo Python 3.11+ is required. & exit /b 1)
where npm >nul 2>nul || (echo Node.js 20.9+ is required: https://nodejs.org/ & exit /b 1)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example ^(demo mode: no API key needed^).
)

echo [1/3] Python environment...
if not exist ".venv" python -m venv .venv
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r apps\api\requirements.txt || exit /b 1

echo [2/3] Web dependencies...
pushd apps\web
call npm install --no-audit --no-fund --silent || (popd & exit /b 1)
popd

echo [3/3] Starting services in two windows...
start "AI Research Agent - API" cmd /k "cd /d "%~dp0apps\api" && "%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000 --reload --reload-dir app"
start "AI Research Agent - Web" cmd /k "cd /d "%~dp0apps\web" && npm run dev"

echo.
echo   Web app : http://localhost:3000
echo   API docs: http://localhost:8000/api/docs
endlocal
