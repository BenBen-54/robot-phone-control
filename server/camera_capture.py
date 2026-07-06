from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def capture_camera_image_data(
    device: str = "/dev/video0",
    width: int = 1280,
    height: int = 720,
) -> dict[str, Any]:
    """Capture one JPEG frame from a Linux V4L2 camera and return a data URL."""
    device = device or "/dev/video0"
    width = _clamp_int(width, 320, 1920, 1280)
    height = _clamp_int(height, 240, 1080, 720)

    if os.name != "nt" and not Path(device).exists():
        return {
            "ok": False,
            "error": f"Camera device not found: {device}",
            "hint": "Run: ls -l /dev/video*",
        }

    errors: list[str] = []
    for capture_method in (_capture_with_fswebcam, _capture_with_opencv, _capture_with_ffmpeg):
        result = capture_method(device, width, height)
        if result["ok"]:
            return result
        errors.append(f"{capture_method.__name__}: {result.get('error') or result.get('detail')}")

    return {
        "ok": False,
        "error": "Camera capture failed",
        "detail": " | ".join(errors),
        "hint": "On Atlas, run: apt-get install -y fswebcam v4l-utils",
    }


def _capture_with_fswebcam(device: str, width: int, height: int) -> dict[str, Any]:
    if not shutil.which("fswebcam"):
        return {"ok": False, "error": "fswebcam is not installed"}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        output_path = temp_file.name

    command = [
        "fswebcam",
        "-d",
        device,
        "-r",
        f"{width}x{height}",
        "-S",
        "3",
        "--no-banner",
        "--jpeg",
        "95",
        output_path,
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        if completed.returncode != 0:
            return {
                "ok": False,
                "error": completed.stderr.strip() or completed.stdout.strip() or "fswebcam failed",
            }
        return _image_file_to_result(output_path, "fswebcam", device, width, height)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        _remove_file(output_path)


def _capture_with_opencv(device: str, width: int, height: int) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"OpenCV is not installed: {exc}"}

    index = _device_to_index(device)
    capture = cv2.VideoCapture(index)
    try:
        if not capture.isOpened():
            return {"ok": False, "error": f"OpenCV cannot open {device}"}
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        frame = None
        for _ in range(5):
            ok, frame = capture.read()
            if ok and frame is not None:
                break
        if frame is None:
            return {"ok": False, "error": "OpenCV did not return a frame"}
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        if not ok:
            return {"ok": False, "error": "OpenCV failed to encode JPEG"}
        image_data = "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
        return {
            "ok": True,
            "capture_method": "opencv",
            "device": device,
            "width": width,
            "height": height,
            "image_data": image_data,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        capture.release()


def _capture_with_ffmpeg(device: str, width: int, height: int) -> dict[str, Any]:
    if not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg is not installed"}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        output_path = temp_file.name

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "video4linux2",
        "-s",
        f"{width}x{height}",
        "-i",
        device,
        "-frames:v",
        "1",
        output_path,
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        if completed.returncode != 0:
            return {
                "ok": False,
                "error": completed.stderr.strip() or completed.stdout.strip() or "ffmpeg failed",
            }
        return _image_file_to_result(output_path, "ffmpeg", device, width, height)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        _remove_file(output_path)


def _image_file_to_result(path: str, method: str, device: str, width: int, height: int) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if not data:
        return {"ok": False, "error": "Captured image is empty"}
    image_data = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
    return {
        "ok": True,
        "capture_method": method,
        "device": device,
        "width": width,
        "height": height,
        "image_data": image_data,
    }


def _device_to_index(device: str) -> int:
    if device.startswith("/dev/video"):
        suffix = device.removeprefix("/dev/video")
        if suffix.isdigit():
            return int(suffix)
    return 0


def _clamp_int(value: int, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(minimum, min(maximum, parsed))


def _remove_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass
