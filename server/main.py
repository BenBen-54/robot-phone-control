from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from robot_adapter import MockRobotAdapter, ZysRobotAdapter


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def build_app(robot_mode: str = "mock") -> FastAPI:
    robot = ZysRobotAdapter() if robot_mode == "real" else MockRobotAdapter()
    app = FastAPI(title="Robot Phone Control")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "robot_mode": robot_mode}

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
                    robot.stop()
                    await ws.send_json({"type": "error", "message": str(exc)})
        except WebSocketDisconnect:
            robot.stop()

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--robot-mode", choices=["mock", "real"], default="mock")
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()
    uvicorn.run(build_app(args.robot_mode), host=args.host, port=args.port)

