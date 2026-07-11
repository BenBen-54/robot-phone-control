#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "Warning: this installer was prepared for Atlas aarch64."
fi

echo "[1/3] Installing RapidOCR and the Python 3.9 ARM64 ONNX Runtime wheel"
.venv/bin/python -m pip install -r requirements-rapidocr-atlas.txt

echo "[2/3] Checking imports"
.venv/bin/python - <<'PY'
import cv2
import onnxruntime
import rapidocr

print("opencv:", cv2.__version__)
print("onnxruntime:", onnxruntime.__version__)
print("providers:", onnxruntime.get_available_providers())
print("rapidocr:", getattr(rapidocr, "__version__", "installed"))
PY

echo "[3/3] Initializing bundled OCR models"
.venv/bin/rapidocr check

echo "RapidOCR install complete."
