@echo off
echo Starting F1 League Agent...
cd /d "%~dp0.."
python -m agent.launcher
pause
