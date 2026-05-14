@echo off
setlocal
pushd "%~dp0.."

echo ============================================
echo   F1 League Agent - Source Install
echo ============================================
echo.
echo This script prepares a local Python environment for running
echo the launcher from source. It is not the distribution flow for
echo other drivers - use Setup_F1LeagueAgent.exe for that.
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ was not found in PATH.
    popd
    endlocal
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv agent_venv
if errorlevel 1 goto :fail

call agent_venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install --no-cache-dir -r agent\requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Ready.
echo.
echo Run the launcher from source with:
echo   call agent_venv\Scripts\activate.bat
echo   python -m agent.launcher
echo.
echo Build the distributable launcher with:
echo   agent\build_launcher.bat
echo.

popd
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Source install failed.
popd
endlocal
exit /b 1
