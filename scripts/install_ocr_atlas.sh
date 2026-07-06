#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/3] Install system OCR packages"
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-chi-sim

echo "[2/3] Install Python OCR packages"
.venv/bin/python -m pip install pillow pytesseract

echo "[3/3] Check OCR engine"
tesseract --version

echo
echo "OCR install complete."
