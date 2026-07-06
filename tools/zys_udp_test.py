from __future__ import annotations

import argparse
import socket
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable


ROBOT_PORT = 9999
DEFAULT_PASSWORD = "88888888"
DEFAULT_ROBOT_IP = "192.168.4.1"


@dataclass
class ParsedPacket:
    source: tuple[str, int]
    pmsg: int
    device: int | None
    command: int | None
    params: bytes
    raw: bytes
    checksum_ok: bool


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def packet_checksum(body_without_header: bytes) -> int:
    # Protocol: check = ~(PMSG + RSE + DATA_Length + DATA...)
    return (~sum(body_without_header)) & 0xFF


def build_short_packet(device: int, command: int, params: bytes = b"", ack: bool = False) -> bytes:
    if not 0 <= device <= 0xFF:
        raise ValueError("device must be 0-255")
    if not 0 <= command <= 0xFF:
        raise ValueError("command must be 0-255")
    if len(params) > 230:
        raise ValueError("short packet params must be <= 230 bytes")

    data = bytes([device, command, len(params)]) + params
    pmsg = 0x80 if ack else 0x00
    body = bytes([pmsg, 0x00, len(data)]) + data
    return bytes([0xFE, 0xEF]) + body + bytes([packet_checksum(body)])


def parse_packet(raw: bytes, source: tuple[str, int]) -> ParsedPacket | None:
    if len(raw) < 7 or raw[0:2] != b"\xFE\xEF":
        return None

    pmsg = raw[2]
    long_packet = bool(pmsg & 0x40)
    if long_packet:
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
    expected = packet_checksum(body)
    checksum_ok = expected == raw[data_end]

    data = raw[data_start:data_end]
    device = data[0] if len(data) >= 1 else None
    command = data[1] if len(data) >= 2 else None
    params = b""
    if len(data) >= 3:
        param_len = data[2]
        params = data[3 : 3 + param_len]

    return ParsedPacket(
        source=source,
        pmsg=pmsg,
        device=device,
        command=command,
        params=params,
        raw=raw,
        checksum_ok=checksum_ok,
    )


def make_socket(local_port: int = ROBOT_PORT) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", local_port))
    except OSError as exc:
        print(f"[警告] 绑定本地 UDP {local_port} 失败：{exc}")
        print("[提示] 请关闭官方 APP、动作编辑器、其他测试脚本后重试。")
        print("[提示] 本次会改用随机本地端口，部分机器人可能不会回包。")
        sock.bind(("", 0))
    print(f"[本机] UDP 监听 {sock.getsockname()[0]}:{sock.getsockname()[1]}")
    return sock


def send_packet(sock: socket.socket, target_ip: str, packet: bytes, label: str) -> None:
    print(f"[发送] {label} -> {target_ip}:{ROBOT_PORT}")
    print(f"       {hex_bytes(packet)}")
    sock.sendto(packet, (target_ip, ROBOT_PORT))


def receive_packets(sock: socket.socket, seconds: float = 1.0) -> list[ParsedPacket]:
    packets: list[ParsedPacket] = []
    deadline = time.time() + seconds
    sock.settimeout(0.15)
    while time.time() < deadline:
        try:
            raw, source = sock.recvfrom(2048)
        except socket.timeout:
            continue
        parsed = parse_packet(raw, source)
        if parsed is None:
            print(f"[收到] {source[0]}:{source[1]} 非协议包 {hex_bytes(raw)}")
            continue
        packets.append(parsed)
        device = "--" if parsed.device is None else f"{parsed.device:02X}"
        command = "--" if parsed.command is None else f"{parsed.command:02X}"
        ok = "OK" if parsed.checksum_ok else "BAD"
        print(
            f"[收到] {source[0]}:{source[1]} "
            f"device=0x{device} cmd=0x{command} checksum={ok} "
            f"params={hex_bytes(parsed.params)}"
        )
    if not packets:
        print("[收到] 没有收到回包。")
    return packets


def find_robot(sock: socket.socket, wait_seconds: float = 1.5) -> str | None:
    search_packet = build_short_packet(0x0A, 0x73)
    targets = ["255.255.255.255", "192.168.4.255", DEFAULT_ROBOT_IP]
    seen: set[str] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        send_packet(sock, target, search_packet, "搜索机器人")
    packets = receive_packets(sock, wait_seconds)
    candidates = [
        packet
        for packet in packets
        if packet.device == 0x0A
        and packet.command == 0x73
        and packet.checksum_ok
        and len(packet.params) >= 8
    ]
    if not candidates:
        print("[提示] 没有找到带 MAC 信息的搜索响应。空 params 的 0x0A/0x73 通常是本机广播回环，不是真机器人。")
        return None

    candidates.sort(key=lambda packet: (not packet.source[0].startswith("192.168.4."), packet.source[0]))
    packet = candidates[0]
    print(f"[发现] 机器人 IP 可能是：{packet.source[0]}")
    mac = ":".join(f"{byte:02X}" for byte in packet.params[:6])
    print(f"[发现] MAC: {mac}")
    if len(packet.params) >= 8:
        print(f"[发现] 武器编号: {packet.params[6]}  是否有密码: {packet.params[7]}")
    if len(packet.params) > 8:
        name = packet.params[8:].decode("utf-8", errors="replace")
        print(f"[发现] 名称: {name}")
    return packet.source[0]
    return None


def require_robot_ip(sock: socket.socket, robot_ip: str | None) -> str:
    if robot_ip:
        return robot_ip
    print("[步骤] 没有指定机器人 IP，先尝试自动搜索。")
    found = find_robot(sock)
    if found:
        return found
    print(f"[提示] 未搜到机器人，将尝试默认 AP 地址 {DEFAULT_ROBOT_IP}。")
    return DEFAULT_ROBOT_IP


def auth(sock: socket.socket, robot_ip: str, password: str) -> None:
    params = password.encode("ascii")
    send_packet(sock, robot_ip, build_short_packet(0x0A, 0x71, params), "授权/登录")
    receive_packets(sock, 1.0)


def query_auth_status(sock: socket.socket, robot_ip: str) -> None:
    send_packet(sock, robot_ip, build_short_packet(0x0A, 0x72, bytes([0])), "查询授权状态")
    receive_packets(sock, 0.8)


def query_battery(sock: socket.socket, robot_ip: str) -> None:
    send_packet(sock, robot_ip, build_short_packet(0x08, 0x03), "查询电池")
    packets = receive_packets(sock, 1.0)
    for packet in packets:
        if packet.device == 0x08 and packet.command == 0x03 and len(packet.params) >= 6:
            battery = int.from_bytes(packet.params[0:2], "little", signed=False)
            voltage_mv = int.from_bytes(packet.params[2:4], "little", signed=False)
            current_ma = int.from_bytes(packet.params[4:6], "little", signed=True)
            print(f"[电池] 剩余 {battery}%  电压 {voltage_mv}mV  电流 {current_ma}mA")


def query_chassis_mode(sock: socket.socket, robot_ip: str) -> None:
    send_packet(sock, robot_ip, build_short_packet(0x08, 0x01), "查询底盘模式")
    receive_packets(sock, 0.8)


def set_chassis_mode(sock: socket.socket, robot_ip: str, mode: int) -> None:
    send_packet(sock, robot_ip, build_short_packet(0x08, 0x01, bytes([mode])), f"设置底盘模式 {mode}")
    receive_packets(sock, 0.6)


def query_chassis_state(sock: socket.socket, robot_ip: str, state_type: int) -> None:
    label = "当前运行参数" if state_type == 1 else "目标运行参数"
    send_packet(sock, robot_ip, build_short_packet(0x08, 0x07, bytes([state_type])), f"查询底盘{label}")
    receive_packets(sock, 0.8)


def send_move(sock: socket.socket, robot_ip: str, angle: int, speed: int, turn: int) -> None:
    params = struct.pack("<hhh", angle, speed, turn)
    send_packet(sock, robot_ip, build_short_packet(0x08, 0x02, params), f"底盘移动 angle={angle} speed={speed} turn={turn}")


def send_timed_move(sock: socket.socket, robot_ip: str, angle: int, speed: int, turn: int, runtime_ms: int) -> None:
    params = struct.pack("<hhhh", angle, speed, turn, runtime_ms)
    packet_via_command_06 = build_short_packet(0x08, 0x06, params)
    send_packet(
        sock,
        robot_ip,
        packet_via_command_06,
        f"底盘定时移动 cmd=0x06 angle={angle} speed={speed} turn={turn} runtime={runtime_ms}ms",
    )


def stop(sock: socket.socket, robot_ip: str) -> None:
    send_move(sock, robot_ip, angle=0, speed=0, turn=0)
    receive_packets(sock, 0.4)


def safe_move(sock: socket.socket, robot_ip: str, angle: int, speed: int, turn: int, duration: float) -> None:
    speed = max(0, min(speed, 30))
    turn = max(-300, min(turn, 300))
    duration = max(0.05, min(duration, 1.0))
    print("[安全] 本脚本会限制 speed<=30, |turn|<=300, duration<=1.0s。")
    send_move(sock, robot_ip, angle, speed, turn)
    receive_packets(sock, 0.2)
    time.sleep(duration)
    print("[安全] 自动发送停止。")
    stop(sock, robot_ip)


def safe_timed_move(sock: socket.socket, robot_ip: str, angle: int, speed: int, turn: int, runtime_ms: int) -> None:
    speed = max(0, min(speed, 30))
    turn = max(-300, min(turn, 300))
    runtime_ms = max(100, min(runtime_ms, 1000))
    print("[安全] 本脚本会限制 speed<=30, |turn|<=300, runtime<=1000ms。")
    send_timed_move(sock, robot_ip, angle, speed, turn, runtime_ms)
    receive_packets(sock, 0.4)
    time.sleep(runtime_ms / 1000 + 0.1)
    print("[安全] 定时移动后再次发送停止。")
    stop(sock, robot_ip)


def run_action(sock: socket.socket, robot_ip: str, action_id: int) -> None:
    if not 0 <= action_id <= 8:
        raise ValueError("action id should be 0-8 for the first test")
    send_packet(sock, robot_ip, build_short_packet(0x07, 0x55, bytes([action_id])), f"执行动作 {action_id}")
    receive_packets(sock, 0.8)


def print_packet_examples() -> None:
    examples: Iterable[tuple[str, bytes]] = [
        ("搜索机器人", build_short_packet(0x0A, 0x73)),
        ("授权 88888888", build_short_packet(0x0A, 0x71, DEFAULT_PASSWORD.encode("ascii"))),
        ("查询电池", build_short_packet(0x08, 0x03)),
        ("停止", build_short_packet(0x08, 0x02, struct.pack("<hhh", 0, 0, 0))),
        ("前进 angle=0 speed=10 turn=0", build_short_packet(0x08, 0x02, struct.pack("<hhh", 0, 10, 0))),
        ("左转 angle=0 speed=0 turn=150", build_short_packet(0x08, 0x02, struct.pack("<hhh", 0, 0, 150))),
        ("普攻 action=4", build_short_packet(0x07, 0x55, bytes([4]))),
    ]
    for label, packet in examples:
        print(f"{label}: {hex_bytes(packet)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智元素格斗机器人 UDP 协议第一步测试工具")
    parser.add_argument("--robot-ip", help=f"机器人 IP；AP 模式通常可先试 {DEFAULT_ROBOT_IP}")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"机器人密码，默认 {DEFAULT_PASSWORD}")
    parser.add_argument("--local-port", type=int, default=ROBOT_PORT, help="本机 UDP 监听端口，默认 9999")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("packets", help="只打印常用命令的十六进制数据包，不连接机器人")
    sub.add_parser("search", help="搜索机器人")
    sub.add_parser("auth", help="授权/登录机器人")
    sub.add_parser("auth-status", help="查询授权状态")
    sub.add_parser("battery", help="查询电池")
    sub.add_parser("stop", help="发送停止命令")
    sub.add_parser("chassis-mode", help="查询底盘模式")
    sub.add_parser("chassis-state", help="查询底盘当前和目标运行参数")

    mode_parser = sub.add_parser("mode", help="设置底盘模式，普通遥控先用 0")
    mode_parser.add_argument("mode", type=int, choices=[0, 2])

    move_parser = sub.add_parser("move", help="低速移动一小段时间，然后自动停止")
    move_parser.add_argument("--angle", type=int, default=0, help="底盘方向角，0=前进，180=后退，90=左移，270=右移")
    move_parser.add_argument("--speed", type=int, default=10, help="速度 0-30，脚本会自动限幅")
    move_parser.add_argument("--turn", type=int, default=0, help="转弯率 -300 到 300，正数左转，负数右转")
    move_parser.add_argument("--duration", type=float, default=0.25, help="持续时间 0.05-1.0 秒，随后自动停止")

    timed_move_parser = sub.add_parser("timed-move", help="使用协议里的定时移动命令测试一小段时间")
    timed_move_parser.add_argument("--angle", type=int, default=0, help="底盘方向角，0=前进，180=后退，90=左移，270=右移")
    timed_move_parser.add_argument("--speed", type=int, default=10, help="速度 0-30，脚本会自动限幅")
    timed_move_parser.add_argument("--turn", type=int, default=0, help="转弯率 -300 到 300，正数左转，负数右转")
    timed_move_parser.add_argument("--runtime-ms", type=int, default=300, help="运行时间 100-1000 毫秒")

    action_parser = sub.add_parser("action", help="执行手臂/武器动作")
    action_parser.add_argument("action_id", type=int, help="0-3=动作1-4, 4=普攻, 5=失败, 6=胜利, 7=开机, 8=战斗开始")

    sub.add_parser("diag", help="诊断：搜索、授权、查授权、查底盘模式、查电池、查底盘状态")
    sub.add_parser("demo", help="推荐第一次运行：搜索、授权、查电池、停止")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "packets":
        print_packet_examples()
        return 0

    sock = make_socket(args.local_port)
    try:
        if args.command == "search":
            find_robot(sock)
            return 0

        robot_ip = require_robot_ip(sock, args.robot_ip)

        if args.command == "auth":
            auth(sock, robot_ip, args.password)
        elif args.command == "auth-status":
            auth(sock, robot_ip, args.password)
            query_auth_status(sock, robot_ip)
        elif args.command == "battery":
            auth(sock, robot_ip, args.password)
            query_battery(sock, robot_ip)
        elif args.command == "stop":
            auth(sock, robot_ip, args.password)
            stop(sock, robot_ip)
        elif args.command == "mode":
            auth(sock, robot_ip, args.password)
            set_chassis_mode(sock, robot_ip, args.mode)
        elif args.command == "chassis-mode":
            auth(sock, robot_ip, args.password)
            query_chassis_mode(sock, robot_ip)
        elif args.command == "chassis-state":
            auth(sock, robot_ip, args.password)
            query_chassis_state(sock, robot_ip, 1)
            query_chassis_state(sock, robot_ip, 2)
        elif args.command == "move":
            auth(sock, robot_ip, args.password)
            safe_move(sock, robot_ip, args.angle, args.speed, args.turn, args.duration)
        elif args.command == "timed-move":
            auth(sock, robot_ip, args.password)
            safe_timed_move(sock, robot_ip, args.angle, args.speed, args.turn, args.runtime_ms)
        elif args.command == "action":
            auth(sock, robot_ip, args.password)
            run_action(sock, robot_ip, args.action_id)
        elif args.command == "diag":
            found = find_robot(sock)
            if found:
                robot_ip = found
            auth(sock, robot_ip, args.password)
            query_auth_status(sock, robot_ip)
            query_chassis_mode(sock, robot_ip)
            query_battery(sock, robot_ip)
            query_chassis_state(sock, robot_ip, 1)
            query_chassis_state(sock, robot_ip, 2)
        elif args.command == "demo":
            auth(sock, robot_ip, args.password)
            query_battery(sock, robot_ip)
            stop(sock, robot_ip)
            print("[完成] demo 没有主动移动机器人；下一步可以在架空轮子后测试 move。")
    except KeyboardInterrupt:
        print("\n[中断] 正在发送停止。")
        if "robot_ip" in locals():
            stop(sock, robot_ip)
        return 130
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
