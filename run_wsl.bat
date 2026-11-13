@echo off
rem ==============================================================================
rem Windows Launcher that delegates execution into WSL
rem ==============================================================================
setlocal
set SCRIPT_DIR=%~dp0
echo [TaskScheduler] Triggering Job Search Monitor in WSL...
wsl.exe bash -c "cd \"$(wslpath '%SCRIPT_DIR%')\" && chmod +x run_wsl.sh && ./run_wsl.sh"
exit /b %ERRORLEVEL%

