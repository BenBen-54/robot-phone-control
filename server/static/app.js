let ws;
const statusEl = document.querySelector("#status");
const logEl = document.querySelector("#log");
const speedEl = document.querySelector("#speed");
const speedValueEl = document.querySelector("#speed-value");
const ocrFileEl = document.querySelector("#ocr-file");
const ocrPreviewEl = document.querySelector("#ocr-preview");
const ocrResultEl = document.querySelector("#ocr-result");
const templatePhraseEl = document.querySelector("#template-phrase");
const autoScanStatusEl = document.querySelector("#auto-scan-status");

let autoScanTimer = null;
let autoScanBusy = false;
let autoScanHits = 0;
let autoScanLastTriggeredAt = 0;

const moves = {
  forward: { angle: 0, turn: 0 },
  backward: { angle: 180, turn: 0 },
  left: { angle: 90, turn: 0 },
  right: { angle: 270, turn: 0 },
  turn_left: { angle: 0, speed: 0, turn: 180 },
  turn_right: { angle: 0, speed: 0, turn: -180 },
};

function log(message) {
  const time = new Date().toLocaleTimeString();
  logEl.textContent = `[${time}] ${message}\n${logEl.textContent}`.slice(0, 4000);
}

async function copyLog() {
  const text = logEl.textContent;
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    log("日志已复制");
  } catch (error) {
    log(`日志复制失败 ${error}`);
  }
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

function speak(text) {
  if (!("speechSynthesis" in window)) {
    log("当前浏览器不支持语音播报");
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function postJson(url, payload, timeoutMs = 25000) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (error) {
      return {
        ok: false,
        error: `服务器返回了非 JSON 响应：HTTP ${response.status}`,
        detail: text.slice(0, 500),
      };
    }
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function runOcr() {
  const file = ocrFileEl.files[0];
  if (!file) {
    ocrResultEl.textContent = "请选择图片";
    return;
  }

  const imageData = await fileToDataUrl(file);
  ocrPreviewEl.src = imageData;
  ocrPreviewEl.hidden = false;
  ocrResultEl.textContent = "识别中...";

  try {
    const result = await postJson("/api/ocr", { image_data: imageData });
    log(`OCR ${JSON.stringify(result)}`);
    showOcrResult(result);
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "识别请求超时" : "识别请求失败";
    log(`OCR 请求失败 ${error}`);
  }
}

async function cameraSnapshot() {
  ocrResultEl.textContent = "摄像头拍照中...";
  try {
    const result = await postJson("/api/camera/snapshot", {}, 12000);
    log(`CAMERA SNAPSHOT ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (!result.ok) {
      ocrResultEl.textContent = result.error || "摄像头拍照失败";
      return;
    }
    ocrPreviewEl.src = result.image_data;
    ocrPreviewEl.hidden = false;
    ocrResultEl.textContent = `已拍照：${result.capture_method || "camera"}`;
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "摄像头请求超时" : "摄像头请求失败";
    log(`摄像头请求失败 ${error}`);
  }
}

async function cameraOcr() {
  ocrResultEl.textContent = "摄像头拍照识别中...";
  try {
    const result = await postJson("/api/camera/ocr", {}, 25000);
    log(`CAMERA OCR ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (result.image_data) {
      ocrPreviewEl.src = result.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(result);
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "摄像头识别请求超时" : "摄像头识别请求失败";
    log(`摄像头识别请求失败 ${error}`);
  }
}

async function taskCardRun() {
  ocrResultEl.textContent = "快速识别任务卡中...";
  try {
    const result = await postJson("/api/camera/task-card", {}, 12000);
    log(`TASK CARD ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (result.image_data) {
      ocrPreviewEl.src = result.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(result);
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "任务卡识别请求超时" : "任务卡识别请求失败";
    log(`任务卡识别请求失败 ${error}`);
  }
}

async function templateCalibrate() {
  ocrResultEl.textContent = "正在校准任务卡...";
  try {
    const result = await postJson(
      "/api/camera/template/calibrate",
      { phrase: templatePhraseEl.value || "位置一 劈砍" },
      12000,
    );
    log(`TEMPLATE CALIBRATE ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (result.image_data) {
      ocrPreviewEl.src = result.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(result);
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "模板校准请求超时" : "模板校准请求失败";
    log(`模板校准请求失败 ${error}`);
  }
}

async function templateRun() {
  ocrResultEl.textContent = "模板识别中...";
  try {
    const result = await postJson("/api/camera/template/recognize", {}, 12000);
    log(`TEMPLATE RECOGNIZE ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (result.image_data) {
      ocrPreviewEl.src = result.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(result);
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "模板识别请求超时" : "模板识别请求失败";
    log(`模板识别请求失败 ${error}`);
  }
}

async function templateExecute() {
  ocrResultEl.textContent = "停车识别并执行中...";
  try {
    const result = await postJson(
      "/api/camera/template/execute",
      { action_id: 4, settle_seconds: 0.4 },
      15000,
    );
    log(`TEMPLATE EXECUTE ${JSON.stringify({ ...result, image_data: result.image_data ? "<image>" : null })}`);
    if (result.image_data) {
      ocrPreviewEl.src = result.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(result);
    if (result.ok && result.matched && result.executed) {
      log(`已执行动作 action_id=${result.action_id}`);
    }
  } catch (error) {
    ocrResultEl.textContent = error.name === "AbortError" ? "停车识别执行超时" : "停车识别执行失败";
    log(`停车识别执行失败 ${error}`);
  }
}

function startAutoScan() {
  if (autoScanTimer) {
    log("轮询识别已经启动");
    return;
  }
  autoScanHits = 0;
  autoScanBusy = false;
  autoScanStatusEl.textContent = "轮询识别中...";
  log("开始轮询识别：连续命中 2 次后自动停车执行");
  autoScanTick();
  autoScanTimer = window.setInterval(autoScanTick, 1200);
}

function stopAutoScan() {
  if (autoScanTimer) {
    window.clearInterval(autoScanTimer);
    autoScanTimer = null;
  }
  autoScanBusy = false;
  autoScanHits = 0;
  autoScanStatusEl.textContent = "轮询已停止";
  log("停止轮询识别");
}

async function autoScanTick() {
  if (autoScanBusy) {
    return;
  }
  const now = Date.now();
  if (now - autoScanLastTriggeredAt < 6000) {
    return;
  }

  autoScanBusy = true;
  try {
    const result = await postJson("/api/camera/template/recognize", {}, 9000);
    const score = typeof result.template_score === "number" ? result.template_score.toFixed(3) : "-";
    autoScanStatusEl.textContent = `轮询中：score=${score} 命中=${autoScanHits}/2`;
    log(`AUTO SCAN ${JSON.stringify({
      ok: result.ok,
      matched: result.matched,
      phrase: result.phrase,
      score: result.template_score,
      threshold: result.template_threshold,
    })}`);

    if (!result.ok || !result.matched) {
      autoScanHits = 0;
      return;
    }

    autoScanHits += 1;
    autoScanStatusEl.textContent = `疑似发现任务卡：${autoScanHits}/2`;
    if (autoScanHits < 2) {
      return;
    }

    autoScanLastTriggeredAt = Date.now();
    stopAutoScan();
    autoScanStatusEl.textContent = "已发现任务卡，停车确认中...";
    speak("发现任务卡");
    send({ cmd: "stop" });
    await sleep(500);

    const executeResult = await postJson(
      "/api/camera/template/execute",
      { action_id: 4, settle_seconds: 0.4 },
      15000,
    );
    log(`AUTO EXECUTE ${JSON.stringify({ ...executeResult, image_data: executeResult.image_data ? "<image>" : null })}`);
    if (executeResult.image_data) {
      ocrPreviewEl.src = executeResult.image_data;
      ocrPreviewEl.hidden = false;
    }
    showOcrResult(executeResult);
    autoScanStatusEl.textContent = executeResult.executed ? "已自动执行动作" : "已停车，但确认失败";
  } catch (error) {
    autoScanHits = 0;
    autoScanStatusEl.textContent = error.name === "AbortError" ? "轮询请求超时" : "轮询请求失败";
    log(`轮询识别失败 ${error}`);
  } finally {
    autoScanBusy = false;
  }
}

function showOcrResult(result) {
  if (!result.ok) {
    ocrResultEl.textContent = result.error || "识别失败";
    return;
  }

  const displayText = result.phrase || result.normalized_text || result.raw_text || "未识别";
  ocrResultEl.textContent = displayText;
  if (!result.phrase && result.raw_text) {
    ocrResultEl.textContent = `未匹配：${result.raw_text.replace(/\s+/g, " ")}`;
  }
  if (result.phrase) {
    speak(result.phrase);
  } else {
    speak("未识别到任务");
  }
}

function currentSpeed() {
  return Number(speedEl.value);
}

function movePayload(name) {
  const move = moves[name];
  return {
    cmd: "move",
    angle: move.angle,
    speed: "speed" in move ? move.speed : currentSpeed(),
    turn: move.turn,
  };
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
  const start = (event) => {
    event.preventDefault();
    send(movePayload(name));
  };
  const stop = (event) => {
    event.preventDefault();
    send({ cmd: "stop" });
  };
  button.addEventListener("pointerdown", start);
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointercancel", stop);
  button.addEventListener("pointerleave", stop);
});

document.querySelector("#stop").addEventListener("click", () => send({ cmd: "stop" }));
document.querySelector("#reconnect").addEventListener("click", connect);
document.querySelector("#battery").addEventListener("click", () => send({ cmd: "battery" }));
document.querySelector("#ocr-run").addEventListener("click", runOcr);
document.querySelector("#camera-snapshot").addEventListener("click", cameraSnapshot);
document.querySelector("#camera-ocr").addEventListener("click", cameraOcr);
document.querySelector("#task-card-run").addEventListener("click", taskCardRun);
document.querySelector("#template-calibrate").addEventListener("click", templateCalibrate);
document.querySelector("#template-run").addEventListener("click", templateRun);
document.querySelector("#template-execute").addEventListener("click", templateExecute);
document.querySelector("#auto-scan-start").addEventListener("click", startAutoScan);
document.querySelector("#auto-scan-stop").addEventListener("click", stopAutoScan);
document.querySelector("#copy-log").addEventListener("click", copyLog);
document.querySelector("#clear-log").addEventListener("click", () => {
  logEl.textContent = "";
});
document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => send({ cmd: "action", action_id: Number(button.dataset.action) }));
});
document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => send({ cmd: "mode", mode: Number(button.dataset.mode) }));
});
speedEl.addEventListener("input", () => {
  speedValueEl.textContent = speedEl.value;
});

connect();

