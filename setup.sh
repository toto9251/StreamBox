#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=========================================================="
echo "       StreamBox (ssto-dl) - Automated Setup (UNIX)"
echo "=========================================================="
echo

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 not found. Please install Python 3.10+ (e.g. sudo apt install python3 python3-venv)"
    exit 1
fi

echo "[+] Python version: $(python3 --version)"

# 2. Virtual Environment
if [ ! -f "venv/bin/python" ]; then
    echo "[*] Creating virtual environment (venv)..."
    python3 -m venv venv
    echo "[+] Virtual environment created."
fi

# 3. Dependencies
echo "[*] Installing Python dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -e . || venv/bin/pip install -r requirements.txt

# 4. Patchright browser
echo "[*] Installing Patchright Chromium browser..."
venv/bin/patchright install chromium

# 5. Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "[!] Warning: ffmpeg was not found in PATH."
    echo "[!] Please install ffmpeg (e.g. 'sudo apt install ffmpeg' or 'brew install ffmpeg')."
else
    echo "[+] FFmpeg is available."
fi

echo
echo "=========================================================="
echo "[+] Setup completed successfully!"
echo "[+] Start the application anytime using ./start.sh"
echo "=========================================================="
