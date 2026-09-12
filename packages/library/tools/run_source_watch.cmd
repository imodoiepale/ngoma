@echo off
REM Durable entry point for the EPALLE daily source watch.
REM Registered as a Windows Scheduled Task so it survives reboots and Claude sessions.
setlocal
set "TOOLS=%~dp0"
set "LOGDIR=%TOOLS%..\manifests\watch-reports"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f "tokens=1-3 delims=/-. " %%a in ("%DATE%") do set "STAMP=%%c%%b%%a"
python "%TOOLS%source_watch.py" >> "%LOGDIR%\watch-run-%STAMP%.log" 2>&1
exit /b %ERRORLEVEL%
