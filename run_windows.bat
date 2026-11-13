@echo off
setlocal
cd /d "%~dp0"
echo Starting Job Search Monitor (Windows Native)...
python main.py --once
exit /b %ERRORLEVEL%

