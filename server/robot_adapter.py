from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from typing import Any


ROBOT_PORT = 9999
DEFAULT_ROBOT_IP = "192.168.4.1"
DEFAULT_PASSWORD = "88888888"


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
        if cmd == "battery":
            return {"cmd": cmd, "battery": 80, "voltage_mv": 12000, "current_ma": 0}
        if cmd == "mode":
            return {"cmd": cmd, "mode": int(message.get("mode", 0)), "state": "ok"}
        if cmd == "action":
            return {"cmd": cmd, "action_id": int(message.get("action_id", 4)), "state": "ok"}
        raise ValueError(f"unknown command: {cmd}")

    def stop(self) -> dict[str, Any]:
        print("[mock] stop")
        return {"cmd": "stop", "state": "stopped"}


def _hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _checksum(body_without_header: bytes) -> int:
    return (~sum(body_without_header)) & 0xFF


def _short_packet(device: int, command: int, params: bytes = b"") -> bytes:
    data = bytes([device, command, len(params)]) + params
    body = bytes([0x00, 0x00, len(data)]) + data
    return bytes([0xFE, 0xEF]) + body + bytes([_checksum(body)])


def _parse_packet(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 7 or raw[:2] != b"\xFE\xEF":
        return None

    pmsg = raw[2]
    if pmsg & 0x40:
        if len(raw) < 8:
            return None
        data_len = (raw[4] << 8) | raw[5]
        data_start = 6
    else:
        data_len = raw[4]
        data_start = 5

    data_end = data_start + data_len
    if len(raw) < data_end + 1:
        return None

    body = raw[2:data_end]
    data = raw[data_start:data_end]
    params = b""
    if len(data) >= 3:
        params = data[3 : 3 + data[2]]

    return {
        "pmsg": pmsg,
        "device": data[0] if len(data) >= 1 else None,
        "command": data[1] if len(data) >= 2 else None,
        "params": params,
        "checksum_ok": _checksum(body) == raw[data_end],
        "raw": raw,
    }


class ZysUdpRobotAdapter(MockRobotAdapter):
    """Control the ZhiYuansu robot directly with the documented UDP protocol."""

    def __init__(
        self,
        robot_ip: str = DEFAULT_ROBOT_IP,
        password: str = DEFAULT_PASSWORD,
        local_port: int = ROBOT_PORT,
    ) -> None:
        self.robot_ip = robot_ip
        self.password = password
        self.last_auth_at = 0.0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.15)
        self.sock.bind(("", local_port))

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        cmd = message.get("cmd")
        if cmd == "move":
            self._ensure_auth()
            angle, speed, turn = self._movement_from_message(message)
            self._send_move(angle, speed, turn)
            return {"cmd": cmd, "state": "moving", "angle": angle, "speed": speed, "turn": turn}
        if cmd == "stop":
            return self.stop()
        if cmd == "battery":
            self._ensure_auth()
            return {"cmd": cmd, **self.query_battery()}
        if cmd == "mode":
            self._ensure_auth()
            mode = int(message.get("mode", 0))
            self._send(_short_packet(0x08, 0x01, bytes([mode])), "mode")
            return {"cmd": cmd, "state": "sent", "mode": mode}
        if cmd == "action":
            self._ensure_auth()
            action_id = int(message.get("action_id", 4))
            self.run_action(action_id)
            return {"cmd": cmd, "state": "sent", "action_id": action_id}
        if cmd == "shoot":
            self._ensure_auth()
            self.run_action(4)
            return {"cmd": cmd, "state": "sent", "action_id": 4}
        raise ValueError(f"unknown command: {cmd}")

    def stop(self) -> dict[str, Any]:
        self._ensure_auth()
        self._send_move(0, 0, 0)
        return {"cmd": "stop", "state": "stopped"}

    def query_battery(self) -> dict[str, Any]:
        packets = self._send(_short_packet(0x08, 0x03), "battery", wait_seconds=0.8)
        for packet in packets:
            if packet.get("device") == 0x08 and packet.get("command") == 0x03:
                params = packet["params"]
                if len(params) >= 6:
                    return {
                        "battery": int.from_bytes(params[0:2], "little", signed=False),
                        "voltage_mv": int.from_bytes(params[2:4], "little", signed=False),
                        "current_ma": int.from_bytes(params[4:6], "little", signed=True),
                    }
        return {"battery": None, "voltage_mv": None, "current_ma": None}

    def run_action(self, action_id: int) -> None:
        action_id = max(0, min(action_id, 8))
        self._send(_short_packet(0x07, 0x55, bytes([action_id])), "action")

    def _ensure_auth(self) -> None:
        if time.time() - self.last_auth_at < 3:
            return
        params = self.password.encode("ascii")
        packets = self._send(_short_packet(0x0A, 0x71, params), "auth", wait_seconds=0.8)
        for packet in packets:
            if packet.get("device") == 0x0A and packet.get("command") == 0x71 and packet["params"][:1] == b"\x01":
                self.last_auth_at = time.time()
                return
        raise RuntimeError("robot authorization failed")

    def _send(self, packet: bytes, label: str, wait_seconds: float = 0.15) -> list[dict[str, Any]]:
        print(f"[udp] {label} -> {self.robot_ip}:{ROBOT_PORT} {_hex_bytes(packet)}")
        self.sock.sendto(packet, (self.robot_ip, ROBOT_PORT))
        packets: list[dict[str, Any]] = []
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            try:
                raw, _source = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            parsed = _parse_packet(raw)
            if parsed and parsed.get("checksum_ok"):
                packets.append(parsed)
        return packets

    def _send_move(self, angle: int, speed: int, turn: int) -> None:
        angle = int(angle) % 360
        speed = max(0, min(int(speed), 35))
        turn = max(-350, min(int(turn), 350))
        params = struct.pack("<hhh", angle, speed, turn)
        self._send(_short_packet(0x08, 0x02, params), "move")

    def _movement_from_message(self, message: dict[str, Any]) -> tuple[int, int, int]:
        if "angle" in message or "speed" in message or "turn" in message:
            return (
                int(message.get("angle", 0)),
                int(message.get("speed", 0)),
                int(message.get("turn", 0)),
            )

        vx = float(message.get("vx", 0))
        vy = float(message.get("vy", 0))
        wz = float(message.get("wz", 0))
        if abs(wz) > 0:
            return (0, 0, int(wz * 300))
        if abs(vx) >= abs(vy):
            return (0 if vx >= 0 else 180, int(abs(vx) * 100), 0)
        return (90 if vy >= 0 else 270, int(abs(vy) * 100), 0)


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

