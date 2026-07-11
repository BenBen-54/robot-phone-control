from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .types import AutonomyState, Decision, Detection, FrameObservation, MotionCommand


STOP = MotionCommand()


@dataclass(frozen=True)
class MissionConfig:
    detection_confidence: float = 0.55
    center_tolerance: float = 0.08
    pillar_stop_area: float = 0.16
    card_read_area: float = 0.10
    gong_action_area: float = 0.18
    approach_speed: int = 7
    orbit_speed: int = 6
    search_turn: int = 100
    max_turn: int = 120
    lost_frame_limit: int = 3
    default_state_timeout: float = 45.0


class MissionController:
    """Pure mission logic. This class never opens a camera or serial port."""

    def __init__(self, config: Optional[MissionConfig] = None) -> None:
        self.config = config or MissionConfig()
        self.state = AutonomyState.IDLE
        self._entered_at = 0.0
        self._lost_frames = 0
        self._task_phrase: Optional[str] = None
        self._action_id: Optional[int] = None
        self._action_emitted = False

    def start(self, now: float) -> Decision:
        self._task_phrase = None
        self._action_id = None
        self._action_emitted = False
        self._transition(AutonomyState.SEARCH_PILLAR, now)
        return self._decision(STOP, "mission started")

    def stop(self, now: float, reason: str = "mission stopped") -> Decision:
        self._transition(AutonomyState.IDLE, now)
        return self._decision(STOP, reason)

    def tick(self, observation: FrameObservation) -> Decision:
        now = observation.now
        if self.state in (AutonomyState.IDLE, AutonomyState.DONE, AutonomyState.FAILSAFE):
            return self._decision(STOP, self.state.value)

        if now - self._entered_at > self._timeout_for(self.state):
            self._transition(AutonomyState.FAILSAFE, now)
            return self._decision(STOP, "state timeout")

        handlers = {
            AutonomyState.SEARCH_PILLAR: self._search_pillar,
            AutonomyState.APPROACH_PILLAR: self._approach_pillar,
            AutonomyState.ORBIT_PILLAR: self._orbit_pillar,
            AutonomyState.ALIGN_CARD: self._align_card,
            AutonomyState.READ_TASK: self._read_task,
            AutonomyState.SEARCH_GONG: self._search_gong,
            AutonomyState.APPROACH_GONG: self._approach_gong,
            AutonomyState.EXECUTE_ACTION: self._execute_action,
        }
        handler = handlers.get(self.state)
        if handler is None:
            self._transition(AutonomyState.FAILSAFE, now)
            return self._decision(STOP, "no state handler")
        return handler(observation)

    def _search_pillar(self, observation: FrameObservation) -> Decision:
        pillar = self._best_detection(observation, "pillar")
        if pillar is None:
            return self._decision(
                MotionCommand(turn=self.config.search_turn),
                "searching for pillar",
            )
        self._transition(AutonomyState.APPROACH_PILLAR, observation.now)
        return self._approach_target(pillar, self.config.pillar_stop_area, "pillar acquired")

    def _approach_pillar(self, observation: FrameObservation) -> Decision:
        pillar = self._best_detection(observation, "pillar")
        if pillar is None:
            return self._handle_lost_target(observation.now, AutonomyState.SEARCH_PILLAR, "pillar lost")
        self._lost_frames = 0
        if pillar.area_ratio >= self.config.pillar_stop_area and self._is_centered(pillar):
            self._transition(AutonomyState.ORBIT_PILLAR, observation.now)
            return self._orbit_command(pillar, "pillar approach complete")
        return self._approach_target(pillar, self.config.pillar_stop_area, "approaching pillar")

    def _orbit_pillar(self, observation: FrameObservation) -> Decision:
        card = self._best_detection(observation, "task_card")
        if card is not None:
            self._transition(AutonomyState.ALIGN_CARD, observation.now)
            return self._approach_target(card, self.config.card_read_area, "task card found")

        pillar = self._best_detection(observation, "pillar")
        if pillar is None:
            return self._handle_lost_target(observation.now, AutonomyState.SEARCH_PILLAR, "pillar lost while orbiting")
        self._lost_frames = 0
        return self._orbit_command(pillar, "orbiting pillar")

    def _align_card(self, observation: FrameObservation) -> Decision:
        card = self._best_detection(observation, "task_card")
        if card is None:
            return self._handle_lost_target(observation.now, AutonomyState.ORBIT_PILLAR, "task card lost")
        self._lost_frames = 0
        if card.area_ratio >= self.config.card_read_area and self._is_centered(card):
            self._transition(AutonomyState.READ_TASK, observation.now)
            return self._decision(STOP, "task card aligned", request_ocr=True)
        return self._approach_target(card, self.config.card_read_area, "aligning task card")

    def _read_task(self, observation: FrameObservation) -> Decision:
        action_id = self._action_for_phrase(observation.task_phrase)
        if action_id is None:
            return self._decision(STOP, "waiting for valid OCR task", request_ocr=True)
        self._task_phrase = observation.task_phrase
        self._action_id = action_id
        self._transition(AutonomyState.SEARCH_GONG, observation.now)
        return self._decision(STOP, f"task accepted: {self._task_phrase}")

    def _search_gong(self, observation: FrameObservation) -> Decision:
        gong = self._best_detection(observation, "gong")
        if gong is None:
            return self._decision(
                MotionCommand(turn=self.config.search_turn),
                "searching for gong",
            )
        self._transition(AutonomyState.APPROACH_GONG, observation.now)
        return self._approach_target(gong, self.config.gong_action_area, "gong acquired")

    def _approach_gong(self, observation: FrameObservation) -> Decision:
        gong = self._best_detection(observation, "gong")
        if gong is None:
            return self._handle_lost_target(observation.now, AutonomyState.SEARCH_GONG, "gong lost")
        self._lost_frames = 0
        if gong.area_ratio >= self.config.gong_action_area and self._is_centered(gong):
            self._transition(AutonomyState.EXECUTE_ACTION, observation.now)
            return self._decision(STOP, "gong aligned; stop before action")
        return self._approach_target(gong, self.config.gong_action_area, "approaching gong")

    def _execute_action(self, observation: FrameObservation) -> Decision:
        if self._action_id is None:
            self._transition(AutonomyState.FAILSAFE, observation.now)
            return self._decision(STOP, "missing task action")
        if not self._action_emitted:
            self._action_emitted = True
            return self._decision(STOP, "execute task action", action_id=self._action_id)
        self._transition(AutonomyState.DONE, observation.now)
        return self._decision(STOP, "mission complete")

    def _approach_target(self, target: Detection, stop_area: float, reason: str) -> Decision:
        error = target.center_x - 0.5
        turn = self._turn_for_error(error)
        speed = 0 if abs(error) > 0.20 else self.config.approach_speed
        if target.area_ratio >= stop_area:
            speed = 0
        return self._decision(MotionCommand(angle=0, speed=speed, turn=turn), reason)

    def _orbit_command(self, pillar: Detection, reason: str) -> Decision:
        # Keep the pillar left of image center while moving laterally around it.
        error = pillar.center_x - 0.35
        turn = self._turn_for_error(error)
        return self._decision(
            MotionCommand(angle=90, speed=self.config.orbit_speed, turn=turn),
            reason,
        )

    def _turn_for_error(self, error: float) -> int:
        turn = int(round(-error * 300))
        return max(-self.config.max_turn, min(self.config.max_turn, turn))

    def _is_centered(self, detection: Detection) -> bool:
        return abs(detection.center_x - 0.5) <= self.config.center_tolerance

    def _best_detection(self, observation: FrameObservation, label: str) -> Optional[Detection]:
        candidates = [
            detection
            for detection in observation.detections
            if detection.label == label and detection.confidence >= self.config.detection_confidence
        ]
        return max(candidates, key=lambda item: (item.confidence, item.area_ratio), default=None)

    def _handle_lost_target(
        self,
        now: float,
        recovery_state: AutonomyState,
        reason: str,
    ) -> Decision:
        self._lost_frames += 1
        if self._lost_frames >= self.config.lost_frame_limit:
            self._transition(recovery_state, now)
            return self._decision(STOP, f"{reason}; entering recovery")
        return self._decision(STOP, f"{reason}; safety stop")

    def _transition(self, state: AutonomyState, now: float) -> None:
        self.state = state
        self._entered_at = now
        self._lost_frames = 0

    def _decision(
        self,
        motion: MotionCommand,
        reason: str,
        request_ocr: bool = False,
        action_id: Optional[int] = None,
    ) -> Decision:
        return Decision(
            state=self.state,
            motion=motion,
            reason=reason,
            request_ocr=request_ocr,
            action_id=action_id,
        )

    def _timeout_for(self, state: AutonomyState) -> float:
        overrides: Dict[AutonomyState, float] = {
            AutonomyState.READ_TASK: 20.0,
            AutonomyState.EXECUTE_ACTION: 10.0,
        }
        return overrides.get(state, self.config.default_state_timeout)

    @staticmethod
    def _action_for_phrase(phrase: Optional[str]) -> Optional[int]:
        normalized = (phrase or "").replace(" ", "").replace("\n", "")
        if "劈砍" not in normalized:
            return None
        if "位置2" in normalized or "任务2" in normalized:
            return 1
        if "位置1" in normalized or "任务1" in normalized:
            return 0
        return None
