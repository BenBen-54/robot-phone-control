from __future__ import annotations

import base64
import os
import re
import threading
from typing import Any, Optional


_ENGINE: Any = None
_ENGINE_LOCK = threading.Lock()


def recognize_task_rapidocr_from_image_data(image_data: str) -> dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        return {
            "ok": False,
            "error": "RapidOCR image dependencies are not installed",
            "detail": str(exc),
        }

    try:
        raw = _decode_image_data(image_data)
        encoded = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            return {"ok": False, "error": "RapidOCR could not decode the camera image"}

        engine = _get_engine()
        output = engine(image, use_det=True, use_cls=True, use_rec=True)
        texts = list(getattr(output, "txts", None) or [])
        scores = [float(score) for score in (getattr(output, "scores", None) or [])]

        # RapidOCR 1.x returned (result, elapsed). Keep this fallback so an older
        # preinstalled package still gives a useful error or result.
        if not texts and isinstance(output, tuple) and len(output) == 2:
            old_results, _elapsed = output
            if old_results:
                texts = [str(item[1][0]) for item in old_results]
                scores = [float(item[1][1]) for item in old_results]

        lines = [
            {"text": text, "score": round(scores[index], 4) if index < len(scores) else None}
            for index, text in enumerate(texts)
        ]
        parsed = parse_expected_task(texts, scores)
        elapsed = getattr(output, "elapse", None)
        if elapsed is not None:
            elapsed = round(float(elapsed), 3)
        return {
            "ok": True,
            "engine": "rapidocr",
            "raw_text": "\n".join(texts),
            "lines": lines,
            "ocr_elapsed": elapsed,
            **parsed,
        }
    except Exception as exc:
        return {"ok": False, "error": "RapidOCR failed", "detail": str(exc)}


def parse_expected_task(texts: list[str], scores: Optional[list[float]] = None) -> dict[str, Any]:
    scores = scores or []
    compact_lines = [_normalize_line(text) for text in texts if text]
    compact = "".join(compact_lines)

    position = _find_position(compact)
    action = _find_action(compact)
    phrase = f"{position} {action}" if position and action else None

    relevant_scores = []
    for index, line in enumerate(compact_lines):
        if index >= len(scores):
            continue
        if _find_position(line) or _find_action(line):
            relevant_scores.append(float(scores[index]))
    if relevant_scores:
        ocr_score = min(relevant_scores)
    elif scores:
        ocr_score = max(float(score) for score in scores)
    else:
        ocr_score = 0.0

    min_confidence = float(os.environ.get("RAPIDOCR_MIN_CONFIDENCE", "0.60"))
    matched = bool(phrase) and ocr_score >= min_confidence
    return {
        "normalized_text": compact,
        "position": position,
        "action": action,
        "phrase": phrase if matched else None,
        "candidate_phrase": phrase,
        "matched": matched,
        "ocr_score": round(ocr_score, 4),
        "ocr_min_confidence": min_confidence,
    }


def _get_engine() -> Any:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            try:
                from rapidocr import RapidOCR
            except Exception as exc:
                raise RuntimeError(
                    "RapidOCR is not installed; run scripts/install_rapidocr_atlas.sh"
                ) from exc
            _ENGINE = RapidOCR()
    return _ENGINE


def _decode_image_data(image_data: str) -> bytes:
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    return base64.b64decode(image_data)


def _normalize_line(text: str) -> str:
    normalized = re.sub(r"\s+", "", text)
    normalized = normalized.replace("：", "").replace(":", "")
    normalized = normalized.replace("位罝", "位置").replace("位署", "位置")
    normalized = normalized.replace("任努", "任务").replace("任条", "任务")
    normalized = re.sub(r"(位置|任务)[Il|]", r"\g<1>1", normalized)
    normalized = re.sub(r"(位置|任务)[Zz]", r"\g<1>2", normalized)
    for wrong in ("劈饮", "劈吹", "劈坎", "劈欣", "辟砍"):
        normalized = normalized.replace(wrong, "劈砍")
    return normalized


def _find_position(text: str) -> Optional[str]:
    match = re.search(r"(?:位置|任务)([12一二])", text)
    if not match:
        return None
    number = match.group(1)
    return "位置2" if number in ("2", "二") else "位置1"


def _find_action(text: str) -> Optional[str]:
    return "劈砍" if "劈砍" in text else None
