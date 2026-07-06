#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] Install camera tools"
apt-get update
apt-get install -y fswebcam v4l-utils

echo "[2/3] List camera devices"
ls -l /dev/video* || true
v4l2-ctl --list-devices || true

echo "[3/3] Optional quick capture test"
fswebcam -d /dev/video0 -r 1280x720 -S 3 --no-banner --jpeg 95 /tmp/zys_camera_test.jpg || true
ls -lh /tmp/zys_camera_test.jpg || true

echo
echo "Camera tools install complete."
