let ws;
const statusEl = document.querySelector("#status");
const logEl = document.querySelector("#log");

const moves = {
  forward: { vx: 0.25, vy: 0, wz: 0 },
  backward: { vx: -0.25, vy: 0, wz: 0 },
  left: { vx: 0, vy: 0.25, wz: 0 },
  right: { vx: 0, vy: -0.25, wz: 0 },
  turn_left: { vx: 0, vy: 0, wz: 0.5 },
  turn_right: { vx: 0, vy: 0, wz: -0.5 },
};

function log(message) {
  const time = new Date().toLocaleTimeString();
  logEl.textContent = `[${time}] ${message}\n${logEl.textContent}`.slice(0, 4000);
}

function setStatus(text) {
  statusEl.textContent = text;
}

function send(payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    log("WebSocket 未连接");
    return;
  }
  ws.send(JSON.stringify(payload));
  log(`发送 ${JSON.stringify(payload)}`);
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/control`);
  setStatus("连接中...");

  ws.onopen = () => {
    setStatus("已连接");
    log("WebSocket 已连接");
  };
  ws.onclose = () => {
    setStatus("已断开");
    log("WebSocket 已断开");
  };
  ws.onerror = () => {
    setStatus("连接错误");
    log("WebSocket 连接错误");
  };
  ws.onmessage = (event) => {
    log(`收到 ${event.data}`);
  };
}

document.querySelectorAll("[data-move]").forEach((button) => {
  const name = button.dataset.move;
  const payload = moves[name];
  button.addEventListener("touchstart", (event) => {
    event.preventDefault();
    send({ cmd: "move", ...payload });
  });
  button.addEventListener("mousedown", () => send({ cmd: "move", ...payload }));
  button.addEventListener("touchend", () => send({ cmd: "stop" }));
  button.addEventListener("mouseup", () => send({ cmd: "stop" }));
  button.addEventListener("mouseleave", () => send({ cmd: "stop" }));
});

document.querySelector("#stop").addEventListener("click", () => send({ cmd: "stop" }));
document.querySelector("#shoot").addEventListener("click", () => send({ cmd: "shoot" }));
document.querySelector("#reload").addEventListener("click", () => send({ cmd: "reload" }));
document.querySelector("#reconnect").addEventListener("click", connect);

connect();

