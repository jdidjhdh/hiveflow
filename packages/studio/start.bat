@echo off
chcp 65001 >nul
set ROOT=%~dp0

echo.
echo ========================================
echo   Starting Backend FastAPI (http://127.0.0.1:8000)
echo ========================================
start "HiveFlow Backend" cmd /k "cd /d %ROOT%backend && .\venv\Scripts\activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo ========================================
echo   Starting Frontend Vite (http://localhost:3000)
echo ========================================
start "HiveFlow Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo HiveFlow Studio starting...
echo   Frontend: http://localhost:3000
echo   Backend: http://127.0.0.1:8000
echo   API Docs: http://127.0.0.1:8000/docs
echo.
pause