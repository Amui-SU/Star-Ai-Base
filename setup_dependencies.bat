@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0setup_dependencies.ps1" (
    echo [ERROR] setup_dependencies.ps1 not found in:
    echo %~dp0
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_dependencies.ps1"
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Dependency setup failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo [OK] Dependency setup completed successfully.
pause
endlocal
