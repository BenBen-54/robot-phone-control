from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture stage-two YOLO training images")
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--output", default="stage2/data/raw")
    parser.add_argument("--session", default="")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--seconds", type=float, default=60.0)
    return parser.parse_args()


def camera_index(device: str) -> int:
    suffix = device.removeprefix("/dev/video")
    return int(suffix) if suffix.isdigit() else 0


def main() -> int:
    args = parse_args()
    try:
        import cv2
    except Exception as exc:
        print(f"OpenCV is required: {exc}")
        return 2

    session = args.session or datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output) / session
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(camera_index(args.camera))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not capture.isOpened():
        print(f"Cannot open camera: {args.camera}")
        return 2

    metadata = {
        "session": session,
        "camera": args.camera,
        "requested_width": args.width,
        "requested_height": args.height,
        "interval": args.interval,
        "seconds": args.seconds,
        "images": [],
    }
    started_at = time.monotonic()
    next_capture_at = started_at
    image_index = 0
    print(f"Capturing into {output_dir}. Press Ctrl+C to stop.")
    try:
        while time.monotonic() - started_at < args.seconds:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("Camera frame failed")
                time.sleep(0.1)
                continue
            now = time.monotonic()
            if now < next_capture_at:
                continue
            filename = f"frame-{image_index:06d}.jpg"
            path = output_dir / filename
            if cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95]):
                metadata["images"].append(
                    {
                        "file": filename,
                        "elapsed": round(now - started_at, 3),
                        "width": int(frame.shape[1]),
                        "height": int(frame.shape[0]),
                    }
                )
                image_index += 1
                print(f"\rCaptured {image_index} images", end="", flush=True)
            next_capture_at = now + max(0.1, args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        (output_dir / "session.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"\nDone: {image_index} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
