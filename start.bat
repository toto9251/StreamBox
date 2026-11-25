@echo off
setlocal
cd /d "%~dp0"

title StreamBox (ssto-dl)

:: If venv does not exist, run setup first
if not exist "venv\Scripts\python.exe" (
    echo [!] First-time setup detected. Running setup.bat...
    call setup.bat
    if not exist "venv\Scripts\python.exe" (
        echo [!] Setup failed or was aborted.
        pause
        exit /b 1
    )
)

:: Run the application
venv\Scripts\python.exe main.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Process exited with code %ERRORLEVEL%
    pause
)
