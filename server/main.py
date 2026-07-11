from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from robot_adapter import MockRobotAdapter, ZysRobotAdapter, ZysSerialRobotAdapter, ZysUdpRobotAdapter
from camera_capture import capture_camera_image_data
from template_match import calibrate_task_template, recognize_task_template
from task_actions import action_id_for_task
from vision_ocr import recognize_task_card_visual_from_image_data, recognize_task_from_image_data


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class OcrRequest(BaseModel):
    image_data: str


class ParseTextRequest(BaseModel):
    text: str


class CameraRequest(BaseModel):
    device: str = "/dev/video0"
    width: int = 1280
    height: int = 720


class TemplateCameraRequest(CameraRequest):
    phrase: str = "位置一 劈砍"


class TemplateExecuteRequest(CameraRequest):
    action_id: Optional[int] = None
    settle_seconds: float = 0.4


def build_app(
    robot_mode: str = "mock",
    robot_ip: str = "192.168.4.1",
    robot_password: str = "88888888",
    serial_port: str = "/dev/ttyAMA0",
    serial_baud: int = 115200,
) -> FastAPI:
    if robot_mode == "real":
        robot = ZysRobotAdapter()
    elif robot_mode == "udp":
        robot = ZysUdpRobotAdapter(robot_ip=robot_ip, password=robot_password)
    elif robot_mode == "serial":
        robot = ZysSerialRobotAdapter(port=serial_port, baud=serial_baud)
    else:
        robot = MockRobotAdapter()
    app = FastAPI(title="Robot Phone Control")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "robot_mode": robot_mode,
            "robot_ip": robot_ip if robot_mode == "udp" else None,
            "serial_port": serial_port if robot_mode == "serial" else None,
            "serial_baud": serial_baud if robot_mode == "serial" else None,
        }

    @app.on_event("shutdown")
    def close_robot() -> None:
        close = getattr(robot, "close", None)
        if callable(close):
            close()

    @app.post("/api/ocr")
    def ocr(request: OcrRequest) -> dict[str, Any]:
        return recognize_task_from_image_data(request.image_data)

    @app.post("/api/parse-text")
    def parse_text(request: ParseTextRequest) -> dict[str, Any]:
        from vision_ocr import parse_task_text

        return {"ok": True, "raw_text": request.text, **parse_task_text(request.text)}

    @app.post("/api/camera/snapshot")
    def camera_snapshot(request: CameraRequest) -> dict[str, Any]:
        return capture_camera_image_data(request.device, request.width, request.height)

    @app.post("/api/camera/ocr")
    def camera_ocr(request: CameraRequest) -> dict[str, Any]:
        capture = capture_camera_image_data(request.device, request.width, request.height)
        if not capture.get("ok"):
            return capture
        ocr = recognize_task_from_image_data(capture["image_data"])
        return {
            **ocr,
            "capture": {
                key: value for key, value in capture.items() if key != "image_data"
            },
            "image_data": capture["image_data"],
        }

    @app.post("/api/camera/task-card")
    def camera_task_card(request: CameraRequest) -> dict[str, Any]:
        capture = capture_camera_image_data(request.device, request.width, request.height)
        if not capture.get("ok"):
            return capture
        result = recognize_task_card_visual_from_image_data(capture["image_data"])
        return {
            **result,
            "capture": {
                key: value for key, value in capture.items() if key != "image_data"
            },
            "image_data": capture["image_data"],
        }

    @app.post("/api/camera/template/calibrate")
    def camera_template_calibrate(request: TemplateCameraRequest) -> dict[str, Any]:
        capture = capture_camera_image_data(request.device, request.width, request.height)
        if not capture.get("ok"):
            return capture
        result = calibrate_task_template(capture["image_data"], request.phrase)
        return {
            **result,
            "capture": {
                key: value for key, value in capture.items() if key != "image_data"
            },
            "image_data": capture["image_data"],
        }

    @app.post("/api/camera/template/recognize")
    def camera_template_recognize(request: CameraRequest) -> dict[str, Any]:
        capture = capture_camera_image_data(request.device, request.width, request.height)
        if not capture.get("ok"):
            return capture
        result = recognize_task_template(capture["image_data"])
        return {
            **result,
            "capture": {
                key: value for key, value in capture.items() if key != "image_data"
            },
            "image_data": capture["image_data"],
        }

    @app.post("/api/camera/template/execute")
    def camera_template_execute(request: TemplateExecuteRequest) -> dict[str, Any]:
        robot_steps: list[dict[str, Any]] = []
        try:
            robot_steps.append({"step": "stop", "result": robot.stop()})
        except Exception as exc:
            return {
                "ok": False,
                "error": "机器人停止失败，未执行识别和动作",
                "detail": str(exc),
                "executed": False,
                "robot_steps": robot_steps,
            }

        settle_seconds = max(0.0, min(float(request.settle_seconds), 2.0))
        if settle_seconds:
            time.sleep(settle_seconds)

        capture = capture_camera_image_data(request.device, request.width, request.height)
        if not capture.get("ok"):
            return {
                **capture,
                "executed": False,
                "robot_steps": robot_steps,
            }

        result = recognize_task_template(capture["image_data"])
        if not result.get("ok"):
            return {
                **result,
                "capture": {
                    key: value for key, value in capture.items() if key != "image_data"
                },
                "image_data": capture["image_data"],
                "executed": False,
                "robot_steps": robot_steps,
            }

        if not result.get("matched"):
            return {
                **result,
                "capture": {
                    key: value for key, value in capture.items() if key != "image_data"
                },
                "image_data": capture["image_data"],
                "executed": False,
                "robot_steps": robot_steps,
            }

        mapped_action_id = action_id_for_task(result.get("phrase"))
        if request.action_id is None and mapped_action_id is None:
            return {
                **result,
                "capture": {
                    key: value for key, value in capture.items() if key != "image_data"
                },
                "image_data": capture["image_data"],
                "executed": False,
                "error": "识别成功，但任务没有对应的动作映射",
                "robot_steps": robot_steps,
            }

        action_id = request.action_id if request.action_id is not None else mapped_action_id
        action_id = max(0, min(int(action_id), 8))
        try:
            action_result = robot.handle({"cmd": "action", "action_id": action_id})
            robot_steps.append({"step": "action", "action_id": action_id, "result": action_result})
        except Exception as exc:
            return {
                **result,
                "capture": {
                    key: value for key, value in capture.items() if key != "image_data"
                },
                "image_data": capture["image_data"],
                "executed": False,
                "error": "识别成功，但机器人动作发送失败",
                "detail": str(exc),
                "robot_steps": robot_steps,
            }

        return {
            **result,
            "capture": {
                key: value for key, value in capture.items() if key != "image_data"
            },
            "image_data": capture["image_data"],
            "executed": True,
            "action_id": action_id,
            "robot_steps": robot_steps,
        }

    @app.websocket("/ws/control")
    async def control(ws: WebSocket) -> None:
        await ws.accept()
        await ws.send_json({"type": "hello", "robot_mode": robot_mode})
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    message = json.loads(raw)
                    result = robot.handle(message)
                    await ws.send_json({"type": "ack", "result": result})
                except Exception as exc:
                    try:
                        robot.stop()
                    except Exception as stop_exc:
                        print(f"failed to stop robot after error: {stop_exc}")
                    await ws.send_json({"type": "error", "message": str(exc)})
        except WebSocketDisconnect:
            try:
                robot.stop()
            except Exception as exc:
                print(f"failed to stop robot after disconnect: {exc}")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--robot-mode", choices=["mock", "udp", "serial", "real"], default="mock")
    parser.add_argument("--robot-ip", default="192.168.4.1")
    parser.add_argument("--robot-password", default="88888888")
    parser.add_argument("--serial-port", default="/dev/ttyAMA0")
    parser.add_argument("--serial-baud", type=int, default=115200)
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()
    uvicorn.run(
        build_app(
            args.robot_mode,
            robot_ip=args.robot_ip,
            robot_password=args.robot_password,
            serial_port=args.serial_port,
            serial_baud=args.serial_baud,
        ),
        host=args.host,
        port=args.port,
    )

