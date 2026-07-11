from __future__ import annotations

import unittest

from stage2.autonomy import AutonomyState, Detection, FrameObservation, MissionController


def detection(label: str, area: float, center_x: float = 0.5, confidence: float = 0.95) -> Detection:
    side = area ** 0.5
    return Detection(label, confidence, center_x, 0.5, side, side)


class MissionControllerTest(unittest.TestCase):
    def test_full_task_one_mission(self) -> None:
        controller = MissionController()
        controller.start(0.0)

        decision = controller.tick(FrameObservation(1.0))
        self.assertEqual(AutonomyState.SEARCH_PILLAR, decision.state)
        self.assertNotEqual(0, decision.motion.turn)

        decision = controller.tick(FrameObservation(2.0, (detection("pillar", 0.05),)))
        self.assertEqual(AutonomyState.APPROACH_PILLAR, decision.state)
        self.assertGreater(decision.motion.speed, 0)

        decision = controller.tick(FrameObservation(3.0, (detection("pillar", 0.18),)))
        self.assertEqual(AutonomyState.ORBIT_PILLAR, decision.state)
        self.assertEqual(90, decision.motion.angle)

        decision = controller.tick(FrameObservation(4.0, (detection("task_card", 0.04),)))
        self.assertEqual(AutonomyState.ALIGN_CARD, decision.state)

        decision = controller.tick(FrameObservation(5.0, (detection("task_card", 0.12),)))
        self.assertEqual(AutonomyState.READ_TASK, decision.state)
        self.assertTrue(decision.request_ocr)
        self.assertTrue(decision.motion.stopped)

        decision = controller.tick(FrameObservation(6.0, task_phrase="位置1 劈砍"))
        self.assertEqual(AutonomyState.SEARCH_GONG, decision.state)

        decision = controller.tick(FrameObservation(7.0, (detection("gong", 0.05),)))
        self.assertEqual(AutonomyState.APPROACH_GONG, decision.state)

        decision = controller.tick(FrameObservation(8.0, (detection("gong", 0.20),)))
        self.assertEqual(AutonomyState.EXECUTE_ACTION, decision.state)
        self.assertIsNone(decision.action_id)

        decision = controller.tick(FrameObservation(9.0))
        self.assertEqual(0, decision.action_id)
        self.assertTrue(decision.motion.stopped)

        decision = controller.tick(FrameObservation(10.0))
        self.assertEqual(AutonomyState.DONE, decision.state)

    def test_invalid_ocr_cannot_advance(self) -> None:
        controller = MissionController()
        controller.start(0.0)
        controller.state = AutonomyState.READ_TASK
        decision = controller.tick(FrameObservation(1.0, task_phrase="其他文字"))
        self.assertEqual(AutonomyState.READ_TASK, decision.state)
        self.assertTrue(decision.request_ocr)
        self.assertIsNone(decision.action_id)

    def test_lost_target_stops_before_recovery(self) -> None:
        controller = MissionController()
        controller.start(0.0)
        controller.state = AutonomyState.APPROACH_PILLAR
        for now in (1.0, 2.0):
            decision = controller.tick(FrameObservation(now))
            self.assertTrue(decision.motion.stopped)
            self.assertEqual(AutonomyState.APPROACH_PILLAR, decision.state)
        decision = controller.tick(FrameObservation(3.0))
        self.assertEqual(AutonomyState.SEARCH_PILLAR, decision.state)
        self.assertTrue(decision.motion.stopped)

    def test_state_timeout_enters_failsafe(self) -> None:
        controller = MissionController()
        controller.start(0.0)
        decision = controller.tick(FrameObservation(50.0))
        self.assertEqual(AutonomyState.FAILSAFE, decision.state)
        self.assertTrue(decision.motion.stopped)


if __name__ == "__main__":
    unittest.main()
