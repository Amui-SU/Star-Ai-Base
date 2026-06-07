@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PS_SCRIPT=%PROJECT_ROOT%scripts\dev.ps1"

cd /d "%PROJECT_ROOT%"

if not exist "%PS_SCRIPT%" (
    echo [ERROR] dev runner not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" install
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
