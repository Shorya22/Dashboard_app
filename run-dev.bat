@echo off
REM Runs backend (FastAPI/uvicorn) and frontend (Vite) dev servers, each in its own window.
setlocal
cd /d "%~dp0"

if not exist "backend\.venv" (
    echo Creating backend virtual environment...
    python -m venv backend\.venv
    call backend\.venv\Scripts\pip install -r backend\requirements.txt
)

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    call npm install --prefix frontend
)

start "Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

endlocal
