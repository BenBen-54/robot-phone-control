from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


DEFAULT_PHRASE = "位置1 劈砍"
TEMPLATE_PATH = Path(os.environ.get("TASK_TEMPLATE_PATH", "data/task_templates.json"))


def calibrate_task_template(image_data: str, phrase: str = DEFAULT_PHRASE) -> dict[str, Any]:
    phrase = (phrase or DEFAULT_PHRASE).strip() or DEFAULT_PHRASE
    image = _load_image(image_data)
    current_hashes = _image_hashes(image)
    templates = _load_templates()
    new_template = (
        {
            "phrase": phrase,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "hashes": current_hashes,
        }
    )
    per_phrase = max(1, int(os.environ.get("TASK_TEMPLATES_PER_PHRASE", "3")))
    same_phrase = [item for item in templates if item.get("phrase") == phrase]
    other_phrases = [item for item in templates if item.get("phrase") != phrase]
    templates = other_phrases + (same_phrase + [new_template])[-per_phrase:]
    _save_templates(templates)
    return {
        "ok": True,
        "matched": True,
        "phrase": phrase,
        "position": _position_from_phrase(phrase),
        "action": "劈砍" if "劈砍" in phrase else None,
        "raw_text": f"模板已校准：{phrase}",
        "normalized_text": phrase.replace(" ", ""),
        "template_count": len(templates),
    }


def recognize_task_template(image_data: str) -> dict[str, Any]:
    try:
        templates = _load_templates()
        if not templates:
            return {
                "ok": False,
                "error": "还没有模板，请先点击“校准当前任务卡”。",
                "matched": False,
            }

        image = _load_image(image_data)
        current_hashes = _image_hashes(image)
        matches = []
        for template in templates:
            score, details = _compare_hashes(current_hashes, template.get("hashes") or {})
            matches.append(
                {
                    "phrase": template.get("phrase") or DEFAULT_PHRASE,
                    "score": round(score, 4),
                    "details": details,
                    "created_at": template.get("created_at"),
                }
            )

        if not matches:
            return {
                "ok": False,
                "error": "模板文件存在，但没有可用模板。请重新校准当前任务卡。",
                "matched": False,
            }

        best = max(matches, key=lambda item: item["score"])
        threshold = float(os.environ.get("TASK_TEMPLATE_THRESHOLD", "0.68"))
        competitors = [item for item in matches if item["phrase"] != best["phrase"]]
        competitor_score = max((item["score"] for item in competitors), default=0.0)
        margin = best["score"] - competitor_score
        required_margin = float(os.environ.get("TASK_TEMPLATE_MARGIN", "0.015"))
        matched = best["score"] >= threshold and (not competitors or margin >= required_margin)
        phrase = best["phrase"] if matched else None
        return {
            "ok": True,
            "label": "template_match",
            "raw_text": f"template_score={best['score']:.3f}, threshold={threshold:.3f}",
            "normalized_text": phrase.replace(" ", "") if phrase else "",
            "position": _position_from_phrase(phrase),
            "action": "劈砍" if phrase and "劈砍" in phrase else None,
            "phrase": phrase,
            "matched": matched,
            "template_score": best["score"],
            "template_threshold": threshold,
            "template_margin": round(margin, 4),
            "template_required_margin": required_margin,
            "matches": matches,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": "模板识别内部错误",
            "detail": f"{type(exc).__name__}: {exc}",
            "matched": False,
        }


def _load_image(image_data: str) -> Any:
    from PIL import Image

    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    raw = base64.b64decode(image_data)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _image_hashes(image: Any) -> dict[str, str]:
    from PIL import ImageFilter, ImageOps

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)
    variants = {
        "full": gray,
        "center80": _crop_center(gray, 0.8),
        "center60": _crop_center(gray, 0.6),
        "upper_center": _crop_ratio(gray, 0.18, 0.10, 0.82, 0.55),
        "lower_center": _crop_ratio(gray, 0.18, 0.42, 0.82, 0.90),
    }
    hashes: dict[str, str] = {}
    for name, variant in variants.items():
        hashes[f"{name}_ahash16"] = _average_hash(variant, 16)
        hashes[f"{name}_dhash16"] = _difference_hash(variant, 16, 16)
    return hashes


def _average_hash(image: Any, size: int) -> str:
    small = image.resize((size, size))
    pixels = list(small.getdata())
    average = sum(pixels) / max(1, len(pixels))
    bits = ["1" if pixel >= average else "0" for pixel in pixels]
    return _bits_to_hex(bits)


def _difference_hash(image: Any, width: int, height: int) -> str:
    small = image.resize((width + 1, height))
    pixels = list(small.getdata())
    bits = []
    for y in range(height):
        row = pixels[y * (width + 1) : (y + 1) * (width + 1)]
        for x in range(width):
            bits.append("1" if row[x] > row[x + 1] else "0")
    return _bits_to_hex(bits)


def _bits_to_hex(bits: list[str]) -> str:
    bit_string = "".join(bits)
    return f"{int(bit_string, 2):0{len(bit_string) // 4}x}"


def _compare_hashes(current: dict[str, str], template: dict[str, str]) -> tuple[float, dict[str, float]]:
    scores = []
    details: dict[str, float] = {}
    for key, current_hash in current.items():
        template_hash = template.get(key)
        if not template_hash:
            continue
        distance = _hex_hamming_distance(current_hash, template_hash)
        bit_count = min(len(current_hash), len(template_hash)) * 4
        score = 1.0 - (distance / max(1, bit_count))
        details[key] = round(score, 4)
        scores.append(score)
    if not scores:
        return 0.0, details
    return sum(scores) / len(scores), details


def _hex_hamming_distance(left: str, right: str) -> int:
    length = min(len(left), len(right))
    if length <= 0:
        return 0
    try:
        left_int = int(left[:length], 16)
        right_int = int(right[:length], 16)
    except ValueError:
        return length * 4
    return bin(left_int ^ right_int).count("1")


def _crop_center(image: Any, ratio: float) -> Any:
    width, height = image.size
    crop_width = int(width * ratio)
    crop_height = int(height * ratio)
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return image.crop((left, top, left + crop_width, top + crop_height))


def _crop_ratio(image: Any, left: float, top: float, right: float, bottom: float) -> Any:
    width, height = image.size
    return image.crop(
        (
            int(width * left),
            int(height * top),
            int(width * right),
            int(height * bottom),
        )
    )


def _position_from_phrase(phrase: Optional[str]) -> Optional[str]:
    normalized = (phrase or "").replace(" ", "")
    if "位置2" in normalized or "位置二" in normalized:
        return "位置2"
    if "位置1" in normalized or "位置一" in normalized:
        return "位置1"
    return None


def _load_templates() -> list[dict[str, Any]]:
    if not TEMPLATE_PATH.exists():
        return []
    try:
        data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_templates(templates: list[dict[str, Any]]) -> None:
    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
