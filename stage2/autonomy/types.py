from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class AutonomyState(str, Enum):
    IDLE = "idle"
    SEARCH_PILLAR = "search_pillar"
    APPROACH_PILLAR = "approach_pillar"
    ORBIT_PILLAR = "orbit_pillar"
    ALIGN_CARD = "align_card"
    READ_TASK = "read_task"
    SEARCH_GONG = "search_gong"
    APPROACH_GONG = "approach_gong"
    EXECUTE_ACTION = "execute_action"
    DONE = "done"
    FAILSAFE = "failsafe"


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    center_x: float
    center_y: float
    width: float
    height: float

    @property
    def area_ratio(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


@dataclass(frozen=True)
class FrameObservation:
    now: float
    detections: Tuple[Detection, ...] = ()
    task_phrase: Optional[str] = None


@dataclass(frozen=True)
class MotionCommand:
    angle: int = 0
    speed: int = 0
    turn: int = 0

    @property
    def stopped(self) -> bool:
        return self.speed == 0 and self.turn == 0


@dataclass(frozen=True)
class Decision:
    state: AutonomyState
    motion: MotionCommand
    reason: str
    request_ocr: bool = False
    action_id: Optional[int] = None
