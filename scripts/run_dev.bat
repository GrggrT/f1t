@echo off
echo Starting F1 League (development mode)...

:: Backend
start "Backend" cmd /k "cd /d %~dp0.. && python -m uvicorn backend.main:app --reload --port 8000"

:: Frontend
start "Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

:: Bot
start "Bot" cmd /k "cd /d %~dp0.. && python -m bot.main"

echo.
echo Services started:
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API docs: http://localhost:8000/docs
echo.
