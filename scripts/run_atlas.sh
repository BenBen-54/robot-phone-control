#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ROBOT_IP="${ROBOT_IP:-192.168.4.1}"
ROBOT_PASSWORD="${ROBOT_PASSWORD:-88888888}"
PORT="${PORT:-8000}"

echo "Starting Robot Phone Control"
echo "Robot IP: ${ROBOT_IP}"
echo "Port: ${PORT}"

exec .venv/bin/python server/main.py \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --robot-mode udp \
  --robot-ip "${ROBOT_IP}" \
  --robot-password "${ROBOT_PASSWORD}"
