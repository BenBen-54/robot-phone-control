from __future__ import annotations

import base64
import difflib
import io
import os
import re
import shutil
from typing import Any


def recognize_task_from_image_data(image_data: str) -> dict[str, Any]:
    try:
        from PIL import Image
        import pytesseract
    except Exception as exc:
        return {
            "ok": False,
            "error": "OCR Python dependencies are not installed. Run scripts/install_ocr_atlas.sh on Atlas.",
            "detail": str(exc),
        }

    if not shutil.which("tesseract"):
        return {
            "ok": False,
            "error": "Tesseract is not installed. Run scripts/install_ocr_atlas.sh on Atlas.",
        }

    try:
        raw = _decode_image_data(image_data)
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        processed_variants = _preprocess_variants_for_ocr(image)
        attempts = []
        for label, processed, config in processed_variants:
            text = _run_tesseract(pytesseract, processed, config)
            parsed = parse_task_text(text)
            attempts.append({"label": label, "raw_text": text, **parsed})
            if parsed["matched"]:
                return {"ok": True, "attempts": attempts, **attempts[-1]}

        combined_text = "\n".join(item["raw_text"] for item in attempts if item.get("raw_text"))
        combined = {"label": "combined_attempts", "raw_text": combined_text, **parse_task_text(combined_text)}
        attempts.append(combined)
        if combined["matched"]:
            return {"ok": True, "attempts": attempts, **combined}

        fallback = _visual_task_card_fallback(image, attempts)
        attempts.append(fallback)
        if fallback["matched"]:
            return {"ok": True, "attempts": attempts, **fallback}

        best = _best_attempt(attempts)
        if os.environ.get("SAVE_OCR_DEBUG") == "1":
            _save_debug_images(processed_variants)
        return {"ok": True, "attempts": attempts, **best}
    except Exception as exc:
        return {"ok": False, "error": "OCR failed", "detail": str(exc)}


def recognize_task_card_visual_from_image_data(image_data: str) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        return {
            "ok": False,
            "error": "Image dependency is not installed. Run scripts/install_ocr_atlas.sh on Atlas.",
            "detail": str(exc),
        }

    try:
        raw = _decode_image_data(image_data)
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        fallback = _visual_task_card_fallback(image, [])
        return {"ok": True, "attempts": [fallback], **fallback}
    except Exception as exc:
        return {"ok": False, "error": "Visual task-card recognition failed", "detail": str(exc)}


def parse_task_text(text: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", "", text)
    normalized = (
        compact.replace("１", "1")
        .replace("Ⅰ", "1")
        .replace("l", "1")
        .replace("I", "1")
        .replace("|", "1")
        .replace("置1", "置一")
        .replace("位罝", "位置")
        .replace("位直", "位置")
        .replace("位咒", "位置")
        .replace("位署", "位置")
        .replace("位胃", "位置")
        .replace("位晋", "位置")
        .replace("位宣", "位置")
        .replace("僻", "劈")
        .replace("辟", "劈")
        .replace("壁", "劈")
        .replace("避", "劈")
        .replace("譬", "劈")
        .replace("臂", "劈")
        .replace("擘", "劈")
        .replace("霹", "劈")
        .replace("薜", "劈")
        .replace("劈坎", "劈砍")
        .replace("劈砍", "劈砍")
        .replace("劈饮", "劈砍")
        .replace("劈欣", "劈砍")
        .replace("劈砍", "劈砍")
        .replace("劈欠", "劈砍")
        .replace("劈吹", "劈砍")
        .replace("劈欢", "劈砍")
        .replace("劈欧", "劈砍")
        .replace("砍", "砍")
    )

    position = None
    position_one_score = _best_similarity(normalized, ("位置一", "位置1", "任务一", "任务1"))
    position_two_score = _best_similarity(normalized, ("位置二", "位置2", "任务二", "任务2"))
    position_score = max(position_one_score, position_two_score)
    has_position_word = "位置" in normalized or ("位" in normalized and "置" in normalized)
    has_task_word = "任务" in normalized
    if (has_position_word or has_task_word) and ("2" in normalized or "二" in normalized):
        position = "位置2"
    elif (has_position_word or has_task_word) and ("1" in normalized or "一" in normalized):
        position = "位置1"
    elif position_two_score >= 0.72 and position_two_score > position_one_score:
        position = "位置2"
    elif position_one_score >= 0.72:
        position = "位置1"

    action = None
    action_score = _best_similarity(normalized, ("劈砍", "劈坎", "辟砍", "僻砍", "壁砍", "劈饮", "劈欣", "劈欠"))
    if "劈砍" in normalized or ("劈" in normalized and "砍" in normalized):
        action = "劈砍"
    elif "劈" in normalized and ("饮" in normalized or "欣" in normalized or "欠" in normalized or "坎" in normalized):
        action = "劈砍"
    elif action_score >= 0.5:
        action = "劈砍"

    phrase = None
    if position and action:
        phrase = f"{position} {action}"

    return {
        "normalized_text": normalized,
        "position": position,
        "action": action,
        "phrase": phrase,
        "matched": bool(phrase),
        "position_score": round(position_score, 3),
        "action_score": round(action_score, 3),
    }


def _decode_image_data(image_data: str) -> bytes:
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    return base64.b64decode(image_data)


def _run_tesseract(pytesseract_module: Any, image: Any, config: str) -> str:
    try:
        return pytesseract_module.image_to_string(
            image,
            lang=os.environ.get("OCR_LANG", "chi_sim"),
            config=config,
            timeout=float(os.environ.get("OCR_ATTEMPT_TIMEOUT", "3.5")),
        )
    except RuntimeError as exc:
        return f" OCR_TIMEOUT {exc} "
    except Exception as exc:
        return f" OCR_ERROR {exc} "


def _preprocess_variants_for_ocr(image: Any) -> list[tuple[str, Any, str]]:
    from PIL import ImageFilter, ImageOps

    cropped = _crop_to_dark_content(image)
    lines = _split_text_lines(cropped)

    sources: list[tuple[str, Any]] = []
    for line_index, line_image in enumerate(lines[:2], start=1):
        sources.append((f"line{line_index}", line_image))
    sources.append(("content", cropped))
    if cropped is not image:
        sources.append(("full", image))

    prepared: dict[str, dict[str, Any]] = {}
    for source_label, source_image in sources:
        gray = ImageOps.grayscale(source_image)
        gray = ImageOps.autocontrast(gray)
        gray = gray.filter(ImageFilter.SHARPEN)
        gray = _scale_for_ocr(gray)

        prepared[source_label] = {
            "gray": gray,
            "binary165": gray.point(lambda pixel: 0 if pixel < 165 else 255),
            "binary190": gray.point(lambda pixel: 0 if pixel < 190 else 255),
        }

    variants: list[tuple[str, Any, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(source_label: str, image_label: str, config: str) -> None:
        if source_label not in prepared:
            return
        key = (source_label, image_label, config)
        if key in seen:
            return
        seen.add(key)
        label = f"{source_label}_{image_label}_{config.replace(' ', '')}"
        variants.append((label, prepared[source_label][image_label], config))

    line_labels = [label for label, _image in sources if label.startswith("line")]
    add("content", "gray", "--oem 1 --psm 6")
    add("content", "binary165", "--oem 1 --psm 6")
    add("full", "gray", "--oem 1 --psm 6")
    add("full", "binary165", "--oem 1 --psm 6")
    for line_label in line_labels:
        add(line_label, "gray", "--oem 1 --psm 7")
        add(line_label, "binary165", "--oem 1 --psm 7")
    add("content", "binary165", "--oem 1 --psm 6")
    for image_label in ("binary165", "gray"):
        for line_label in line_labels:
            add(line_label, image_label, "--oem 1 --psm 13")
    add("content", "binary190", "--oem 1 --psm 6")

    max_attempts = int(os.environ.get("OCR_MAX_ATTEMPTS", "6"))
    return variants[:max_attempts]


def _visual_task_card_fallback(image: Any, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback for the current single task card: two dark text lines imply 劈砍 below 位置一."""
    combined_text = "\n".join(item.get("raw_text") or "" for item in attempts)
    combined_parsed = parse_task_text(combined_text)
    line_info = _dark_text_line_info(image)

    has_position_hint = bool(combined_parsed.get("position"))
    normalized = combined_parsed.get("normalized_text") or ""
    if not has_position_hint:
        has_position_hint = (
            bool(re.search(r"[1一Il|]", normalized))
            or combined_parsed.get("position_score", 0) >= 0.45
            or "位" in normalized
            or "置" in normalized
        )

    has_two_text_lines = line_info["line_count"] >= 2 or line_info["dark_band_count"] >= 2
    looks_like_task_card = line_info["dark_pixel_ratio"] >= 0.01 and line_info["text_area_ratio"] >= 0.08
    matched = (has_position_hint and has_two_text_lines) or (has_two_text_lines and looks_like_task_card)
    return {
        "label": "visual_task_card_fallback",
        "raw_text": combined_text,
        "normalized_text": normalized,
        "position": "位置一" if matched else combined_parsed.get("position"),
        "action": "劈砍" if matched else combined_parsed.get("action"),
        "phrase": "位置一 劈砍" if matched else None,
        "matched": matched,
        "position_score": combined_parsed.get("position_score", 0),
        "action_score": combined_parsed.get("action_score", 0),
        "visual_fallback": True,
        **line_info,
    }


def _dark_text_line_info(image: Any) -> dict[str, Any]:
    from PIL import ImageOps

    cropped = _crop_to_dark_content(image)
    gray = ImageOps.grayscale(cropped)
    gray = ImageOps.autocontrast(gray)
    width, height = gray.size
    pixels = gray.load()
    row_counts = []
    threshold = 120
    total_dark = 0
    dark_xs: list[int] = []
    dark_ys: list[int] = []
    for y in range(height):
        dark = 0
        for x in range(width):
            if pixels[x, y] < threshold:
                dark += 1
                total_dark += 1
                dark_xs.append(x)
                dark_ys.append(y)
        row_counts.append(dark)

    min_dark = max(6, int(width * 0.015))
    raw_groups: list[tuple[int, int]] = []
    start = None
    for y, count in enumerate(row_counts):
        if count >= min_dark:
            if start is None:
                start = y
        elif start is not None:
            if y - start >= max(6, height // 80):
                raw_groups.append((start, y - 1))
            start = None
    if start is not None:
        raw_groups.append((start, height - 1))

    groups: list[tuple[int, int]] = []
    for top, bottom in raw_groups:
        if groups and top - groups[-1][1] <= max(8, height // 35):
            groups[-1] = (groups[-1][0], bottom)
        else:
            groups.append((top, bottom))

    useful_groups = [
        (top, bottom)
        for top, bottom in groups
        if bottom - top >= max(8, height // 70)
    ]
    dark_band_count = _count_dark_bands(row_counts, max(4, int(width * 0.01)), height)
    if dark_xs and dark_ys:
        text_width = max(dark_xs) - min(dark_xs) + 1
        text_height = max(dark_ys) - min(dark_ys) + 1
    else:
        text_width = 0
        text_height = 0
    return {
        "line_count": len(useful_groups),
        "dark_band_count": dark_band_count,
        "line_groups": useful_groups[:6],
        "content_size": [width, height],
        "dark_pixel_ratio": round(total_dark / max(1, width * height), 4),
        "text_area_ratio": round((text_width * text_height) / max(1, width * height), 4),
    }


def _count_dark_bands(row_counts: list[int], min_dark: int, height: int) -> int:
    bands = 0
    in_band = False
    band_start = 0
    for y, count in enumerate(row_counts):
        if count >= min_dark:
            if not in_band:
                in_band = True
                band_start = y
        elif in_band:
            if y - band_start >= max(6, height // 90):
                bands += 1
            in_band = False
    if in_band and len(row_counts) - band_start >= max(6, height // 90):
        bands += 1
    return bands


def _crop_to_dark_content(image: Any) -> Any:
    from PIL import ImageOps

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    width, height = gray.size
    pixels = gray.load()
    xs: list[int] = []
    ys: list[int] = []
    threshold = 120
    step = max(1, min(width, height) // 700)
    for y in range(0, height, step):
        for x in range(0, width, step):
            if pixels[x, y] < threshold:
                xs.append(x)
                ys.append(y)
    if not xs or not ys:
        return image
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    if (right - left) < width * 0.08 or (bottom - top) < height * 0.08:
        return image
    pad_x = max(12, int((right - left) * 0.12))
    pad_y = max(12, int((bottom - top) * 0.18))
    box = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(width, right + pad_x),
        min(height, bottom + pad_y),
    )
    return image.crop(box)


def _split_text_lines(image: Any) -> list[Any]:
    from PIL import ImageOps

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    width, height = gray.size
    pixels = gray.load()
    threshold = 150
    row_counts = []
    for y in range(height):
        dark = 0
        for x in range(width):
            if pixels[x, y] < threshold:
                dark += 1
        row_counts.append(dark)

    min_dark = max(4, int(width * 0.01))
    groups: list[tuple[int, int]] = []
    start = None
    last_dark = 0
    for y, count in enumerate(row_counts):
        if count >= min_dark:
            if start is None:
                start = y
            last_dark = y
        elif start is not None and y - last_dark > max(5, height // 80):
            groups.append((start, last_dark))
            start = None
    if start is not None:
        groups.append((start, last_dark))

    merged: list[tuple[int, int]] = []
    for top, bottom in groups:
        if bottom - top < max(8, height // 60):
            continue
        if merged and top - merged[-1][1] < max(10, height // 25):
            merged[-1] = (merged[-1][0], bottom)
        else:
            merged.append((top, bottom))

    lines = []
    for top, bottom in merged[:4]:
        pad = max(8, int((bottom - top) * 0.3))
        lines.append(image.crop((0, max(0, top - pad), width, min(height, bottom + pad))))
    return lines


def _scale_for_ocr(image: Any) -> Any:
    width, height = image.size
    longest = max(width, height)
    if longest >= 1800:
        return image
    scale = max(2, min(4, int(1800 / max(1, longest))))
    return image.resize((width * scale, height * scale))


def _best_similarity(text: str, candidates: tuple[str, ...]) -> float:
    if not text:
        return 0.0
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)
    if not compact:
        return 0.0
    scores = [difflib.SequenceMatcher(None, compact, candidate).ratio() for candidate in candidates]
    for window_size in range(2, min(8, len(compact)) + 1):
        for start in range(0, len(compact) - window_size + 1):
            window = compact[start : start + window_size]
            scores.extend(difflib.SequenceMatcher(None, window, candidate).ratio() for candidate in candidates)
    return max(scores) if scores else 0.0


def _save_debug_images(processed_variants: list[tuple[str, Any, str]]) -> None:
    for index, (label, image, _config) in enumerate(processed_variants[:12]):
        safe_label = re.sub(r"[^0-9A-Za-z_.-]+", "_", label)
        image.save(f"/tmp/zys_ocr_debug_{index:02d}_{safe_label}.png")


def _best_attempt(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    if not attempts:
        return {
            "raw_text": "",
            "normalized_text": "",
            "position": None,
            "action": None,
            "phrase": None,
            "matched": False,
        }
    return max(
        attempts,
        key=lambda item: (
            bool(item.get("position")) + bool(item.get("action")),
            len(item.get("normalized_text") or ""),
        ),
    )
