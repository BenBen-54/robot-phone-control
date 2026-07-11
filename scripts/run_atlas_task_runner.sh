#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SERIAL_PORT="${SERIAL_PORT:-/dev/ttyAMA0}"
SERIAL_BAUD="${SERIAL_BAUD:-115200}"
CAMERA="${CAMERA:-/dev/video0}"
RECOGNIZER="${RECOGNIZER:-rapidocr}"
INTERVAL="${INTERVAL:-1.0}"
CONFIRM_HITS="${CONFIRM_HITS:-2}"
COOLDOWN="${COOLDOWN:-8.0}"
REARM_MISSES="${REARM_MISSES:-2}"

extra_args=()
if [[ "${STOP_BEFORE_ACTION:-1}" == "1" ]]; then
  extra_args+=(--stop-before-action)
fi
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  extra_args+=(--dry-run)
fi

exec .venv/bin/python server/atlas_task_runner.py \
  --serial-port "${SERIAL_PORT}" \
  --serial-baud "${SERIAL_BAUD}" \
  --camera "${CAMERA}" \
  --recognizer "${RECOGNIZER}" \
  --interval "${INTERVAL}" \
  --confirm-hits "${CONFIRM_HITS}" \
  --cooldown "${COOLDOWN}" \
  --rearm-misses "${REARM_MISSES}" \
  "${extra_args[@]}"
