#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ ! -f "venv/bin/python" ]; then
    echo "[!] First-time setup detected. Running setup.sh..."
    bash setup.sh
fi

exec venv/bin/python main.py "$@"
