@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\dev.ps1" start
set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% neq 0 (
    pause
    exit /b %EXIT_CODE%
)
