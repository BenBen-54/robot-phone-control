#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="zys-atlas-task-runner.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root."
  exit 1
fi

systemctl disable --now "${SERVICE_NAME}" 2>/dev/null || true
echo "${SERVICE_NAME} is stopped and disabled."
echo "The UART login console remains masked so it cannot take /dev/ttyAMA0."
