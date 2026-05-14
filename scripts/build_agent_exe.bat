@echo off
setlocal
pushd "%~dp0.."
call agent\build_launcher.bat
set EXIT_CODE=%ERRORLEVEL%
popd
endlocal
exit /b %EXIT_CODE%
