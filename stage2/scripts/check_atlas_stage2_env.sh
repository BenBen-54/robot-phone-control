#!/usr/bin/env bash
set -u

echo "== Platform =="
uname -a
python3 --version

echo
echo "== Ascend device =="
if command -v npu-smi >/dev/null 2>&1; then
  npu-smi info
else
  echo "npu-smi: not found"
fi

echo
echo "== Model converter =="
if command -v atc >/dev/null 2>&1; then
  atc --version
else
  echo "atc: not found in PATH"
fi

echo
echo "== Python ACL =="
python3 - <<'PY'
try:
    import acl
    print("acl import: OK")
except Exception as exc:
    print(f"acl import: FAILED: {exc}")
PY

echo
echo "== Camera and serial =="
ls -l /dev/video* /dev/ttyAMA0 2>/dev/null || true

echo
echo "== Stage-one protection =="
systemctl is-enabled zys-atlas-task-runner.service 2>/dev/null || true
systemctl is-active zys-atlas-task-runner.service 2>/dev/null || true
