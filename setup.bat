@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

title StreamBox (ssto-dl) - Automated Setup

echo ==========================================================
echo        StreamBox (ssto-dl) - Automated Setup
echo ==========================================================
echo.

:: 1. Find a real Python 3.10+ interpreter (ignore Windows Store stub)
set "PY_CMD="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
) else (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [!] ERROR: Python 3.10+ was not found on your system!
    echo [*] Trying to install Python 3.12 via winget...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    echo.
    echo [!] If Python was just installed, please close this window,
    echo [!] open a new terminal (or restart PC), and run setup.bat again.
    echo [!] Otherwise download Python 3.10+ from https://www.python.org/downloads/
    echo [!] IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% --version 2^>^&1') do set "PYTHON_VER=%%i"
echo [+] Found %PYTHON_VER% (using: %PY_CMD%)

:: 2. Create virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (venv)...
    %PY_CMD% -m venv venv
    if !ERRORLEVEL! neq 0 (
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

echo [*] Installing dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [!] Failed to install dependencies from requirements.txt.
    pause
    exit /b 1
)

echo [*] Installing StreamBox package...
venv\Scripts\python.exe -m pip install -e . --no-build-isolation >nul 2>&1
if %ERRORLEVEL% neq 0 (
    venv\Scripts\python.exe -m pip install -e .
)

:: 4. Install patchright browser (Chromium)
echo [*] Installing Patchright browser (Chromium)...
venv\Scripts\python.exe -m patchright install chromium

:: 5. Check FFmpeg
echo [*] Checking FFmpeg...
where ffmpeg >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Note: ffmpeg was not found in your system PATH.
    echo [*] Trying to install ffmpeg automatically via winget...
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if !ERRORLEVEL! neq 0 (
        echo [!] Could not auto-install ffmpeg.
        echo [!] Please download ffmpeg from https://ffmpeg.org/download.html and add it to PATH.
    ) else (
        echo [+] FFmpeg installed! Please restart the terminal if ffmpeg is not recognized yet.
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
