@echo off
setlocal
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
cd /d "%~dp0"

title StreamBox (ssto-dl)

:: Check if venv exists AND dependencies are actually installed
set "NEED_SETUP=0"
if not exist "venv\Scripts\python.exe" (
    set "NEED_SETUP=1"
) else (
    venv\Scripts\python.exe -c "import questionary, rich, httpx, selectolax, patchright, yt_dlp" >nul 2>&1
    if errorlevel 1 set "NEED_SETUP=1"
)

if "%NEED_SETUP%"=="1" (
    echo [!] Setup needed or incomplete. Running setup.bat...
    call setup.bat
    if not exist "venv\Scripts\python.exe" (
        echo [!] Setup failed or was aborted.
        pause
        exit /b 1
    )
)

:: Activate venv so yt-dlp and scripts are on PATH, then run
call venv\Scripts\activate.bat
python main.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Process exited with code %ERRORLEVEL%
    pause
)
