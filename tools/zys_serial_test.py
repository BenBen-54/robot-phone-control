from __future__ import annotations

import argparse
import glob
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BAUD = 115200
DEFAULT_PASSWORD = "88888888"
DEFAULT_PROTOCOL = "bridge"
SERIAL_PATTERNS = (
    "/dev/ttyAMA*",
    "/dev/ttyS*",
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
)


@dataclass
class ParsedPacket:
    pmsg: int | None
    device: int | None
    command: int | None
    params: bytes
    raw: bytes
    checksum_ok: bool


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def packet_checksum(body_without_header: bytes) -> int:
    return (~sum(body_without_header)) & 0xFF


def build_short_packet(device: int, command: int, params: bytes = b"") -> bytes:
    if not 0 <= device <= 0xFF:
        raise ValueError("device must be 0-255")
    if not 0 <= command <= 0xFF:
        raise ValueError("command must be 0-255")
    if len(params) > 230:
        raise ValueError("short packet params must be <= 230 bytes")

    data = bytes([device, command, len(params)]) + params
    body = bytes([0x00, 0x00, len(data)]) + data
    return bytes([0xFE, 0xEF]) + body + bytes([packet_checksum(body)])


def build_bridge_packet(device: int, command: int, params: bytes = b"") -> bytes:
    if not 0 <= device <= 0xFF:
        raise ValueError("device must be 0-255")
    if not 0 <= command <= 0xFF:
        raise ValueError("command must be 0-255")
    if len(params) > 150:
        raise ValueError("bridge packet params must be <= 150 bytes")

    body = bytes([device, command, len(params)]) + params
    return bytes([0xF5, 0x5F]) + body + bytes([packet_checksum(body)])


def build_packet(protocol: str, device: int, command: int, params: bytes = b"") -> bytes:
    if protocol == "bridge":
        return build_bridge_packet(device, command, params)
    return build_short_packet(device, command, params)


def parse_packet(raw: bytes) -> ParsedPacket | None:
    if len(raw) >= 6 and raw[0:2] == b"\xF5\x5F":
        param_length = raw[4]
        data_end = 5 + param_length
        if len(raw) < data_end + 1:
            return None
        return ParsedPacket(
            pmsg=None,
            device=raw[2],
            command=raw[3],
            params=raw[5:data_end],
            raw=raw[: data_end + 1],
            checksum_ok=packet_checksum(raw[2:data_end]) == raw[data_end],
        )

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
    data = raw[data_start:data_end]
    params = b""
    if len(data) >= 3:
        params = data[3 : 3 + data[2]]

    return ParsedPacket(
        pmsg=pmsg,
        device=data[0] if len(data) >= 1 else None,
        command=data[1] if len(data) >= 2 else None,
        params=params,
        raw=raw[: data_end + 1],
        checksum_ok=packet_checksum(body) == raw[data_end],
    )


def take_packets(buffer: bytearray) -> list[ParsedPacket]:
    packets: list[ParsedPacket] = []
    while True:
        headers = [
            (position, signature)
            for signature in (b"\xFE\xEF", b"\xF5\x5F")
            if (position := buffer.find(signature)) >= 0
        ]
        if not headers:
            if len(buffer) > 1:
                del buffer[:-1]
            break
        header, signature = min(headers, key=lambda item: item[0])
        if header > 0:
            del buffer[:header]
        if len(buffer) < 5:
            break

        if signature == b"\xF5\x5F":
            total_length = 6 + buffer[4]
        else:
            long_packet = bool(buffer[2] & 0x40)
            if long_packet:
                if len(buffer) < 6:
                    break
                total_length = 6 + ((buffer[4] << 8) | buffer[5]) + 1
            else:
                total_length = 5 + buffer[4] + 1
        if len(buffer) < total_length:
            break

        raw = bytes(buffer[:total_length])
        del buffer[:total_length]
        packet = parse_packet(raw)
        if packet is not None:
            packets.append(packet)
    return packets


def import_serial() -> tuple[Any, Any]:
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        print("[缺少依赖] 当前 Python 没有安装 pyserial。")
        print("[Atlas 终端执行] .venv/bin/python -m pip install pyserial==3.5")
        raise SystemExit(2) from exc
    return serial, list_ports


def list_serial_ports() -> int:
    _, list_ports = import_serial()
    found: dict[str, str] = {}
    for item in list_ports.comports():
        found[item.device] = item.description or "pyserial detected"
    for pattern in SERIAL_PATTERNS:
        for device in glob.glob(pattern):
            found.setdefault(device, "Linux serial device")

    if not found:
        print("[端口] 没有发现候选串口。")
        print("[提示] 40 针硬件 UART 可能未启用，或设备节点名称不在常见列表中。")
        return 1

    print("[端口] 候选串口：")
    for device in sorted(found):
        path = Path(device)
        target = f" -> {path.resolve()}" if path.is_symlink() else ""
        print(f"  {device}{target}  ({found[device]})")
    return 0


def open_port(port: str, baud: int) -> Any:
    serial, _ = import_serial()
    print(f"[串口] 打开 {port}，{baud} baud，8N1")
    try:
        connection = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
            write_timeout=1.0,
        )
    except Exception as exc:
        print(f"[失败] 无法打开串口：{exc}")
        print("[提示] 检查设备节点、串口控制台占用和接线。")
        raise SystemExit(2) from exc
    connection.reset_input_buffer()
    return connection


def print_packet(packet: ParsedPacket) -> None:
    device = "--" if packet.device is None else f"{packet.device:02X}"
    command = "--" if packet.command is None else f"{packet.command:02X}"
    checksum = "OK" if packet.checksum_ok else "BAD"
    print(
        f"[协议包] device=0x{device} cmd=0x{command} "
        f"checksum={checksum} params={hex_bytes(packet.params)}"
    )


def receive_packets(connection: Any, seconds: float) -> list[ParsedPacket]:
    deadline = time.monotonic() + seconds
    buffer = bytearray()
    packets: list[ParsedPacket] = []
    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        data = connection.read(waiting if waiting > 0 else 1)
        if not data:
            continue
        buffer.extend(data)
        for packet in take_packets(buffer):
            packets.append(packet)
            print_packet(packet)

    if buffer:
        print(f"[原始数据] 尚未组成完整协议包：{hex_bytes(bytes(buffer))}")
    if not packets:
        print("[收到] 没有收到完整协议回包。")
    return packets


def send_packet(connection: Any, packet: bytes, label: str, wait: float = 0.8) -> list[ParsedPacket]:
    print(f"[发送] {label}")
    print(f"       {hex_bytes(packet)}")
    connection.write(packet)
    connection.flush()
    return receive_packets(connection, wait)


def authorize(connection: Any, password: str, protocol: str) -> list[ParsedPacket]:
    return send_packet(
        connection,
        build_packet(protocol, 0x0A, 0x71, password.encode("ascii")),
        "授权/登录",
        0.8,
    )


def probe(connection: Any, password: str, protocol: str) -> None:
    print("[探测] 本命令不会发送底盘移动或手臂动作。")
    if protocol == "wifi":
        authorize(connection, password, protocol)
        send_packet(connection, build_packet(protocol, 0x0A, 0x72, bytes([0])), "查询授权状态", 0.6)
    else:
        print("[串口桥接] 厂家 Arduino 协议直接控制，不发送 Wi-Fi 授权包。")
    send_packet(connection, build_packet(protocol, 0x08, 0x03), "查询电池", 0.8)
    print("[完成] 即使没有回包，也先不要改变接线；下一步应对照 TX/RX 活动和波特率继续判断。")


def run_action(
    connection: Any,
    password: str,
    action_id: int,
    confirmed: bool,
    protocol: str,
) -> int:
    if not confirmed:
        print("[安全拦截] 动作会驱动机器人上半身。确认周围安全后添加 --confirm。")
        return 2
    if not 0 <= action_id <= 8:
        print("[错误] action_id 必须在 0-8 之间。")
        return 2

    if protocol == "wifi":
        authorize(connection, password, protocol)
        time.sleep(0.15)
    send_packet(
        connection,
        build_packet(protocol, 0x07, 0x55, bytes([action_id])),
        f"执行动作 action_id={action_id}",
        1.0,
    )
    return 0


def print_packets(password: str, protocol: str) -> None:
    examples = []
    if protocol == "wifi":
        examples.extend(
            (
                ("授权", build_packet(protocol, 0x0A, 0x71, password.encode("ascii"))),
                ("查询授权", build_packet(protocol, 0x0A, 0x72, bytes([0]))),
            )
        )
    examples.extend(
        (
            ("查询电池", build_packet(protocol, 0x08, 0x03)),
            ("停止底盘", build_packet(protocol, 0x08, 0x02, struct.pack("<hhh", 0, 0, 0))),
            ("动作1", build_packet(protocol, 0x07, 0x55, bytes([0]))),
            ("动作2", build_packet(protocol, 0x07, 0x55, bytes([1]))),
        )
    )
    print(f"协议模式: {protocol}")
    for label, packet in examples:
        print(f"{label}: {hex_bytes(packet)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智元素机器人 Atlas UART 安全测试工具")
    parser.add_argument("--port", help="串口设备，例如 /dev/ttyAMA0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="默认 115200")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="默认 88888888")
    parser.add_argument(
        "--protocol",
        choices=("bridge", "wifi"),
        default=DEFAULT_PROTOCOL,
        help="bridge=厂家 F5 5F Arduino 串口协议（默认），wifi=FE EF Wi-Fi 协议",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ports", help="列出候选串口，不连接机器人")
    sub.add_parser("packets", help="只打印协议包，不打开串口")

    listen_parser = sub.add_parser("listen", help="只监听串口，不发送任何数据")
    listen_parser.add_argument("--seconds", type=float, default=5.0, help="默认监听 5 秒")

    sub.add_parser("probe", help="授权并查询状态，不发送动作或移动")
    sub.add_parser("auth", help="只发送授权命令")
    sub.add_parser("stop", help="只发送底盘停止命令")

    action_parser = sub.add_parser("action", help="执行动作1-4或内置动作")
    action_parser.add_argument("action_id", type=int, help="0=动作1, 1=动作2, 4=普攻")
    action_parser.add_argument("--confirm", action="store_true", help="确认上半身周围安全")
    return parser


def require_port(parser: argparse.ArgumentParser, port: str | None) -> str:
    if not port:
        parser.error("该命令必须提供 --port，例如 --port /dev/ttyAMA0")
    return port


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ports":
        return list_serial_ports()
    if args.command == "packets":
        print_packets(args.password, args.protocol)
        return 0

    port = require_port(parser, args.port)
    connection = open_port(port, args.baud)
    try:
        if args.command == "listen":
            print(f"[监听] {args.seconds:.1f} 秒，不发送数据。")
            receive_packets(connection, max(0.1, args.seconds))
        elif args.command == "probe":
            probe(connection, args.password, args.protocol)
        elif args.command == "auth":
            if args.protocol == "bridge":
                print("[串口桥接] 厂家 Arduino 协议不需要 Wi-Fi 授权命令。")
            else:
                authorize(connection, args.password, args.protocol)
        elif args.command == "stop":
            if args.protocol == "wifi":
                authorize(connection, args.password, args.protocol)
            send_packet(
                connection,
                build_packet(args.protocol, 0x08, 0x02, struct.pack("<hhh", 0, 0, 0)),
                "底盘停止",
                0.5,
            )
        elif args.command == "action":
            return run_action(
                connection,
                args.password,
                args.action_id,
                args.confirm,
                args.protocol,
            )
    except KeyboardInterrupt:
        print("\n[中断] 已停止测试；本脚本没有启动底盘移动。")
        return 130
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
