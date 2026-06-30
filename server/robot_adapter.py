from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MoveCommand:
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0


class MockRobotAdapter:
    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        cmd = message.get("cmd")
        if cmd == "move":
            move = MoveCommand(
                vx=float(message.get("vx", 0)),
                vy=float(message.get("vy", 0)),
                wz=float(message.get("wz", 0)),
            )
            print(f"[mock] move vx={move.vx:.2f}, vy={move.vy:.2f}, wz={move.wz:.2f}")
            return {"cmd": cmd, "state": "moving", **move.__dict__}
        if cmd == "stop":
            return self.stop()
        if cmd == "shoot":
            print("[mock] shoot")
            return {"cmd": cmd, "state": "shot"}
        if cmd == "reload":
            print("[mock] reload")
            return {"cmd": cmd, "state": "reloaded"}
        raise ValueError(f"unknown command: {cmd}")

    def stop(self) -> dict[str, Any]:
        print("[mock] stop")
        return {"cmd": "stop", "state": "stopped"}


class ZysRobotAdapter(MockRobotAdapter):
    """Connect this adapter to the official ZhiYuansu SDK on the robot."""

    def __init__(self) -> None:
        try:
            from sdk.uprobot_action import Action  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Could not import the ZhiYuansu SDK. Run from the robot, or add "
                "~/up_ele_base_class_code to PYTHONPATH."
            ) from exc
        self.action = Action()

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        cmd = message.get("cmd")
        if cmd == "move":
            vx = float(message.get("vx", 0))
            vy = float(message.get("vy", 0))
            wz = float(message.get("wz", 0))
            self.move(vx, vy, wz)
            return {"cmd": cmd, "state": "moving", "vx": vx, "vy": vy, "wz": wz}
        if cmd == "stop":
            return self.stop()
        if cmd == "shoot":
            self.shoot()
            return {"cmd": cmd, "state": "shot"}
        if cmd == "reload":
            self.reload()
            return {"cmd": cmd, "state": "reloaded"}
        raise ValueError(f"unknown command: {cmd}")

    def move(self, vx: float, vy: float, wz: float) -> None:
        # TODO: Replace with the real movement call from official test_control.py.
        raise NotImplementedError("Fill in movement call from official test_control.py")

    def stop(self) -> dict[str, Any]:
        # TODO: Replace with the official stop call.
        raise NotImplementedError("Fill in stop call from official test_control.py")

    def shoot(self) -> None:
        # TODO: Replace with the official shoot call.
        raise NotImplementedError("Fill in shoot call from official test_control.py")

    def reload(self) -> None:
        # TODO: Replace with the official reload/load call.
        raise NotImplementedError("Fill in reload call from official test_control.py")

