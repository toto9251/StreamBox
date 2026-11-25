@echo off
setlocal
cd /d "%~dp0"

title Push StreamBox to GitHub

echo ==========================================================
echo        Pushing StreamBox to GitHub
echo ==========================================================
echo.
echo Target: https://github.com/toto9251/StreamBox.git
echo.
git push -u origin main
echo.
if %ERRORLEVEL% equ 0 (
    echo [+] Successfully uploaded to GitHub!
) else (
    echo [!] Push exited with error code %ERRORLEVEL%.
)
echo.
pause
