@echo off
setlocal
pushd "%~dp0"

echo ============================================
echo  Building F1 League Agent Launcher
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  popd
  endlocal
  exit /b 1
)

echo [1/4] Installing launcher build dependencies...
python -m pip install --disable-pip-version-check pyinstaller
if errorlevel 1 goto :fail
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo [2/4] Cleaning previous build output...
if exist build_tmp rmdir /s /q build_tmp
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist installer_output\Setup_F1LeagueAgent.exe del /q installer_output\Setup_F1LeagueAgent.exe

echo [3/4] Building launcher exe...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build_tmp F1LeagueAgent.spec
if errorlevel 1 goto :fail

if not exist dist\F1LeagueAgent.exe (
  echo [ERROR] dist\F1LeagueAgent.exe was not created.
  goto :fail
)

if not exist ..\backend\static mkdir ..\backend\static
copy /y dist\F1LeagueAgent.exe ..\backend\static\F1LeagueAgent.exe >nul

echo [4/4] Building installer...
where ISCC >nul 2>nul
if errorlevel 1 (
  echo [WARN] ISCC.exe was not found. Skipping installer build.
  goto :done
)

ISCC.exe installer.iss
if errorlevel 1 goto :fail

if exist installer_output\Setup_F1LeagueAgent.exe (
  copy /y installer_output\Setup_F1LeagueAgent.exe ..\backend\static\Setup_F1LeagueAgent.exe >nul
)

:done
echo.
echo ============================================
echo  Build complete
echo ============================================
echo EXE:       %CD%\dist\F1LeagueAgent.exe
if exist installer_output\Setup_F1LeagueAgent.exe echo INSTALLER: %CD%\installer_output\Setup_F1LeagueAgent.exe
echo STATIC:    %CD%\..\backend\static

popd
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Launcher packaging failed.
popd
endlocal
exit /b 1
