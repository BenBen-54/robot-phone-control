#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] Python version"
python3 --version

echo "[2/4] Create virtual environment"
python3 -m venv .venv

echo "[3/4] Upgrade pip"
.venv/bin/python -m pip install --upgrade pip

echo "[4/4] Install project requirements"
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Atlas install complete."
echo "Next: ./scripts/run_atlas.sh"
