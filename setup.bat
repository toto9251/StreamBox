@echo off
setlocal enabledelayedexpansion

title StreamBox (ssto-dl) - Automated Setup
cd /d "%~dp0"

echo ==========================================================
echo        StreamBox (ssto-dl) - Automated Setup
echo ==========================================================
echo.

:: 1. Check Python installation
echo [*] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] ERROR: Python was not found on your system!
    echo [!] Please install Python 3.10 or newer from https://www.python.org/downloads/
    echo [!] IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo [+] Found %PYTHON_VER%

:: 2. Create virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (venv)...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created.
) else (
    echo [+] Virtual environment already exists.
)

:: 3. Upgrade pip and install dependencies
echo [*] Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1

echo [*] Installing dependencies from pyproject.toml...
venv\Scripts\pip.exe install -e .
if %ERRORLEVEL% neq 0 (
    echo [!] Retrying with requirements.txt...
    venv\Scripts\pip.exe install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [!] Installation failed.
        pause
        exit /b 1
    )
)

:: 4. Install patchright browser (Chromium)
echo [*] Installing Patchright browser dependencies...
venv\Scripts\patchright.exe install chromium

:: 5. Check FFmpeg
echo [*] Checking FFmpeg...
where ffmpeg >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Note: ffmpeg is not currently in your system PATH.
    echo [*] Trying to install ffmpeg automatically via winget...
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if %ERRORLEVEL% neq 0 (
        echo [!] Could not auto-install ffmpeg.
        echo [!] Please download ffmpeg from https://ffmpeg.org/download.html and add it to PATH.
    ) else (
        echo [+] FFmpeg installed successfully!
    )
) else (
    echo [+] FFmpeg is available.
)

echo.
echo ==========================================================
echo [+] Setup completed successfully!
echo [+] You can now launch the app anytime by double-clicking "start.bat"
echo ==========================================================
echo.
pause
