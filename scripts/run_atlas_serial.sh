#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
SERIAL_PORT="${SERIAL_PORT:-/dev/ttyAMA0}"
SERIAL_BAUD="${SERIAL_BAUD:-115200}"

echo "Starting Robot Phone Control in serial mode"
echo "Serial: ${SERIAL_PORT} @ ${SERIAL_BAUD}"
echo "Web port: ${PORT}"

exec .venv/bin/python server/main.py \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --robot-mode serial \
  --serial-port "${SERIAL_PORT}" \
  --serial-baud "${SERIAL_BAUD}"
