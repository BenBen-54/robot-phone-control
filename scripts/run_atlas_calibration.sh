#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"

echo "Starting Atlas camera calibration web UI"
echo "Robot mode: mock (UART is not opened)"
echo "Web port: ${PORT}"

exec .venv/bin/python server/main.py \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --robot-mode mock
