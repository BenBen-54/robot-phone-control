from __future__ import annotations

from typing import Optional


def normalize_task_phrase(phrase: Optional[str]) -> str:
    return (phrase or "").replace(" ", "").replace("\n", "").strip()


def action_id_for_task(phrase: Optional[str]) -> Optional[int]:
    normalized = normalize_task_phrase(phrase)
    if not normalized or "劈砍" not in normalized:
        return None

    if any(token in normalized for token in ("位置2", "位置二", "任务2", "任务二")):
        return 1
    if any(token in normalized for token in ("位置1", "位置一", "任务1", "任务一")):
        return 0
    return None
