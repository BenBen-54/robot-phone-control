from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from camera_capture import capture_camera_image_data
from robot_adapter import ZysSerialRobotAdapter
from rapidocr_recognizer import recognize_task_rapidocr_from_image_data
from task_actions import action_id_for_task
from template_match import recognize_task_template
from vision_ocr import recognize_task_from_image_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Atlas camera task recognition and UART action runner")
    parser.add_argument("--serial-port", default="/dev/ttyAMA0")
    parser.add_argument("--serial-baud", type=int, default=115200)
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--recognizer",
        choices=("rapidocr", "template", "ocr"),
        default="rapidocr",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--confirm-hits", type=int, default=2)
    parser.add_argument("--cooldown", type=float, default=8.0)
    parser.add_argument("--rearm-misses", type=int, default=2)
    parser.add_argument("--stop-before-action", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--status-file", default="data/atlas_task_runner_status.json")
    return parser.parse_args()


def recognize(image_data: str, recognizer: str) -> dict[str, Any]:
    if recognizer == "rapidocr":
        return recognize_task_rapidocr_from_image_data(image_data)
    if recognizer == "ocr":
        return recognize_task_from_image_data(image_data)
    return recognize_task_template(image_data)


def write_status(path: Path, status: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except Exception as exc:
        print(f"[runner] status write failed: {exc}", flush=True)


def main() -> int:
    args = parse_args()
    interval = max(0.2, float(args.interval))
    confirm_hits = max(1, int(args.confirm_hits))
    cooldown = max(0.0, float(args.cooldown))
    rearm_misses = max(1, int(args.rearm_misses))
    status_path = Path(args.status_file)
    robot = None if args.dry_run else ZysSerialRobotAdapter(args.serial_port, args.serial_baud)

    print("[runner] Atlas task runner started", flush=True)
    print(
        f"[runner] recognizer={args.recognizer} camera={args.camera} "
        f"confirm_hits={confirm_hits} cooldown={cooldown:.1f}s "
        f"rearm_misses={rearm_misses} dry_run={args.dry_run}",
        flush=True,
    )

    consecutive_phrase: Optional[str] = None
    consecutive_hits = 0
    last_trigger_at = 0.0
    latched_phrase: Optional[str] = None
    latch_misses = 0
    iteration = 0

    try:
        while args.max_iterations <= 0 or iteration < args.max_iterations:
            iteration += 1
            started_at = time.monotonic()
            capture = capture_camera_image_data(args.camera, args.width, args.height)
            if not capture.get("ok"):
                consecutive_phrase = None
                consecutive_hits = 0
                status = {
                    "ok": False,
                    "iteration": iteration,
                    "stage": "capture",
                    "error": capture.get("error"),
                    "detail": capture.get("detail"),
                    "updated_at": time.time(),
                }
                print(f"[runner] capture failed: {status['error']}", flush=True)
                write_status(status_path, status)
            else:
                result = recognize(capture["image_data"], args.recognizer)
                phrase = result.get("phrase") if result.get("matched") else None
                action_id = action_id_for_task(phrase)
                score = result.get("template_score")
                if score is None:
                    score = result.get("ocr_score")

                if phrase and action_id is not None:
                    if phrase == consecutive_phrase:
                        consecutive_hits += 1
                    else:
                        consecutive_phrase = phrase
                        consecutive_hits = 1
                else:
                    consecutive_phrase = None
                    consecutive_hits = 0

                if latched_phrase:
                    if phrase is None:
                        latch_misses += 1
                        if latch_misses >= rearm_misses:
                            print(f"[runner] rearmed after {latch_misses} misses", flush=True)
                            latched_phrase = None
                            latch_misses = 0
                    elif phrase != latched_phrase:
                        print(
                            f"[runner] rearmed for new phrase={phrase}",
                            flush=True,
                        )
                        latched_phrase = None
                        latch_misses = 0
                    else:
                        latch_misses = 0

                now = time.monotonic()
                cooldown_remaining = max(0.0, cooldown - (now - last_trigger_at)) if last_trigger_at else 0.0
                blocked_by_latch = bool(phrase and phrase == latched_phrase)
                triggered = False
                if (
                    phrase
                    and action_id is not None
                    and consecutive_hits >= confirm_hits
                    and cooldown_remaining <= 0
                    and not blocked_by_latch
                ):
                    print(
                        f"[runner] confirmed phrase={phrase} action_id={action_id} hits={consecutive_hits}",
                        flush=True,
                    )
                    if args.dry_run:
                        print("[runner] dry-run: action not sent", flush=True)
                    else:
                        if args.stop_before_action:
                            robot.stop()
                            time.sleep(0.35)
                        robot.run_action(action_id)
                    triggered = True
                    last_trigger_at = time.monotonic()
                    latched_phrase = phrase
                    latch_misses = 0
                    consecutive_phrase = None
                    consecutive_hits = 0

                score_text = "-" if score is None else f"{float(score):.3f}"
                ocr_elapsed = result.get("ocr_elapsed")
                ocr_time_text = "-" if ocr_elapsed is None else f"{float(ocr_elapsed):.2f}s"
                processing_elapsed = time.monotonic() - started_at
                raw_text = (result.get("raw_text") or "").replace("\n", " / ")
                print(
                    f"[runner] iteration={iteration} matched={bool(phrase)} phrase={phrase or '-'} "
                    f"score={score_text} hits={consecutive_hits}/{confirm_hits} "
                    f"cooldown={cooldown_remaining:.1f}s triggered={triggered} "
                    f"latched={blocked_by_latch} ocr={ocr_time_text} "
                    f"cycle={processing_elapsed:.2f}s "
                    f"text={raw_text or '-'}",
                    flush=True,
                )
                if not result.get("ok"):
                    print(
                        f"[runner] recognizer failed: {result.get('error')} "
                        f"detail={result.get('detail', '-')}",
                        flush=True,
                    )
                write_status(
                    status_path,
                    {
                        "ok": bool(result.get("ok")),
                        "iteration": iteration,
                        "recognizer": args.recognizer,
                        "matched": bool(phrase),
                        "phrase": phrase,
                        "action_id": action_id,
                        "score": score,
                        "raw_text": result.get("raw_text"),
                        "ocr_elapsed": result.get("ocr_elapsed"),
                        "cycle_elapsed": round(processing_elapsed, 3),
                        "recognizer_error": result.get("error"),
                        "consecutive_hits": consecutive_hits,
                        "confirm_hits": confirm_hits,
                        "cooldown_remaining": round(cooldown_remaining, 2),
                        "triggered": triggered,
                        "latched_phrase": latched_phrase,
                        "blocked_by_latch": blocked_by_latch,
                        "capture_method": capture.get("capture_method"),
                        "updated_at": time.time(),
                    },
                )

            elapsed = time.monotonic() - started_at
            if elapsed < interval:
                time.sleep(interval - elapsed)
    except KeyboardInterrupt:
        print("\n[runner] stopped by user", flush=True)
    finally:
        if robot is not None:
            robot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
