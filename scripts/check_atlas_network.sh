#!/usr/bin/env bash
set -euo pipefail

ROBOT_IP="${ROBOT_IP:-192.168.4.1}"

echo "[Network interfaces]"
ip -4 addr

echo
echo "[Default route]"
ip route || true

echo
echo "[Ping robot: ${ROBOT_IP}]"
ping -c 2 "${ROBOT_IP}"

echo
echo "[UDP robot demo]"
cd "$(dirname "$0")/.."
.venv/bin/python tools/zys_udp_test.py --robot-ip "${ROBOT_IP}" demo
