#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SERVICE_NAME="zys-atlas-task-runner.service"
SERVICE_SOURCE="systemd/${SERVICE_NAME}"
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}"
SYSCTL_SOURCE="systemd/99-zys-uart-console.conf"
SYSCTL_TARGET="/etc/sysctl.d/99-zys-uart-console.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root."
  exit 1
fi

for required in .venv/bin/python scripts/run_atlas_task_runner.sh "${SERVICE_SOURCE}" "${SYSCTL_SOURCE}"; do
  if [[ ! -e "${required}" ]]; then
    echo "Missing required file: ${required}"
    exit 1
  fi
done

if [[ ! -c /dev/ttyAMA0 ]]; then
  echo "Serial device does not exist: /dev/ttyAMA0"
  exit 1
fi

if [[ ! -c /dev/video0 ]]; then
  echo "Camera device does not exist: /dev/video0"
  exit 1
fi

echo "[1/6] Stop and permanently mask the UART login console"
systemctl disable --now serial-getty@ttyAMA0.service 2>/dev/null || true
systemctl mask serial-getty@ttyAMA0.service

echo "[2/6] Verify no old process is using /dev/ttyAMA0"
if fuser /dev/ttyAMA0 >/dev/null 2>&1; then
  echo "ERROR: /dev/ttyAMA0 is still in use."
  fuser -v /dev/ttyAMA0 || true
  echo "Stop the manually started runner with Ctrl+C, then run this installer again."
  exit 1
fi

echo "[3/6] Persist a quiet runtime kernel-console level"
install -m 0644 "${SYSCTL_SOURCE}" "${SYSCTL_TARGET}"
sysctl -p "${SYSCTL_TARGET}"

echo "[4/6] Install the task-runner systemd unit"
install -m 0644 "${SERVICE_SOURCE}" "${SERVICE_TARGET}"
chmod +x scripts/run_atlas_task_runner.sh
systemctl daemon-reload

echo "[5/6] Enable and start ${SERVICE_NAME}"
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[6/6] Show service state"
systemctl status "${SERVICE_NAME}" --no-pager

echo
echo "Autostart installation complete."
echo "Follow logs with: journalctl -u ${SERVICE_NAME} -f"
