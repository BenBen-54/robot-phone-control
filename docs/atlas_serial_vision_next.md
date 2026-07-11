# Atlas 串口动作成功后的视觉识别步骤

本文从以下已验证状态继续：

- 机器人已烧录 `UART1TOUART2.ino`。
- Atlas `/dev/ttyAMA0` 使用 `115200`。
- `F5 5F` 串口帧可以触发动作1和动作2。
- 动作1、动作2已经包含各自录制的语音。

目标映射：

```text
位置1 劈砍 / 任务1 劈砍 -> action_id=0 -> 动作1
位置2 劈砍 / 任务2 劈砍 -> action_id=1 -> 动作2
```

## 1. 重要规则

同一时间只能有一个进程打开 `/dev/ttyAMA0`。运行新的服务前先按 `Ctrl+C` 停止旧服务，并检查：

```bash
fuser -v /dev/ttyAMA0
```

没有输出后才能启动下一个串口程序。

现在提供三种识别模式：

- `rapidocr`：推荐模式，使用 PP-OCR ONNX 中文模型真正读取汉字和数字。
- `template`：整图相似度实验模式。两张卡片只有数字不同，容易把位置1和位置2混淆。
- `ocr`：旧版 Tesseract 实验模式，速度和中文准确率均不作为最终方案。

正式演示使用 `rapidocr`。模板数据只用于早期链路验证，不再要求校准。

## 2. 上传最新代码

Windows 文件：

```text
C:\Users\20914\Documents\robot-phone-control\dist\robot-phone-control-atlas.zip
```

用 MobaXterm 左侧文件区将它上传到 Atlas 的 `/root/`，然后在 Atlas 终端执行：

```bash
cd /root
unzip -o robot-phone-control-atlas.zip -d robot-phone-control
cd /root/robot-phone-control
chmod +x scripts/*.sh
```

检查新版命令：

```bash
.venv/bin/python server/main.py --help
.venv/bin/python server/atlas_task_runner.py --help
.venv/bin/python tools/zys_serial_test.py packets
```

最后一条应显示 `协议模式: bridge` 和 `F5 5F` 数据包。

## 3. 临时释放串口

每次 Atlas 重启后，在永久配置完成前执行：

```bash
systemctl stop serial-getty@ttyAMA0.service
dmesg -n 1
fuser -v /dev/ttyAMA0
```

`fuser` 应没有输出。

## 4. 检查摄像头

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
fswebcam -d /dev/video0 -r 1280x720 -S 3 --no-banner --jpeg 95 /tmp/task-camera.jpg
ls -lh /tmp/task-camera.jpg
```

如果摄像头不是 `/dev/video0`，后续通过环境变量指定，例如：

```bash
CAMERA=/dev/video2
```

## 5. 校准两张任务卡

先启动用于校准的网页服务。校准只使用 Atlas 摄像头，不需要机器人串口，因此使用 `mock` 模式，避免占用 `/dev/ttyAMA0`：

```bash
cd /root/robot-phone-control
./scripts/run_atlas_calibration.sh
```

终端必须保持运行，并看到 `Uvicorn running on http://0.0.0.0:8000`。如果命令立即返回提示符或出现 traceback，说明服务没有启动成功，浏览器也不会打开。

电脑浏览器打开：

```text
http://192.168.0.2:8000
```

校准位置1：

1. 将“位置1 劈砍”任务卡放到答辩时的大致距离和角度。
2. 在模板名称输入框填写 `位置1 劈砍`。
3. 点击“校准当前任务卡”。
4. 稍微改变距离或角度，再校准两次。同一任务最多保留最近三张模板。

校准位置2：

1. 换成“位置2 劈砍”任务卡。
2. 输入框改为 `位置2 劈砍`。
3. 同样校准三次。

完成后在 Atlas 终端按 `Ctrl+C` 停止网页服务，然后检查：

```bash
cat data/task_templates.json
```

文件中应同时存在 `位置1 劈砍` 和 `位置2 劈砍`。

## 6. 干运行验证

干运行只识别和打印日志，不打开串口，也不会让机器人动作：

```bash
cd /root/robot-phone-control
DRY_RUN=1 RECOGNIZER=template ./scripts/run_atlas_task_runner.sh
```

依次把两张任务卡放到摄像头前。连续识别成功时应看到：

```text
[runner] confirmed phrase=位置1 劈砍 action_id=0 hits=2
[runner] dry-run: action not sent
```

以及：

```text
[runner] confirmed phrase=位置2 劈砍 action_id=1 hits=2
[runner] dry-run: action not sent
```

按 `Ctrl+C` 停止。

## 7. 真实自动执行

机器人放稳，确认手臂周围安全，手机摇杆先松开。检查串口没有被占用：

```bash
fuser -v /dev/ttyAMA0
```

启动真实循环：

```bash
cd /root/robot-phone-control
RECOGNIZER=template STOP_BEFORE_ACTION=1 ./scripts/run_atlas_task_runner.sh
```

默认行为：

- 每轮拍摄一张图。
- 同一个任务连续命中两次才确认。
- 先发送底盘停止，再发送动作。
- 位置1执行动作1，位置2执行动作2。
- 每次执行后冷却 8 秒。

状态同时写入：

```text
data/atlas_task_runner_status.json
```

## 8. 安装并运行真实 OCR

Atlas 临时联网后安装 RapidOCR：

```bash
cd /root/robot-phone-control
chmod +x scripts/install_rapidocr_atlas.sh
./scripts/install_rapidocr_atlas.sh
```

先保持干运行，观察终端中的 `text=`、`score=` 和 `phrase=`：

```bash
DRY_RUN=1 RECOGNIZER=rapidocr ./scripts/run_atlas_task_runner.sh
```

只有两张任务卡连续多次识别正确后，才去掉 `DRY_RUN=1`：

```bash
RECOGNIZER=rapidocr STOP_BEFORE_ACTION=1 ./scripts/run_atlas_task_runner.sh
```

同一张任务卡触发后会被锁定。只有任务卡离开画面并连续两次未识别，或者换成另一张任务卡，程序才会重新允许触发，避免卡片一直放在镜头前时每隔几秒重复动作。

## 9. 配置开机自启动

只有完成以下验证后才配置 systemd：

1. 两张任务卡干运行均能正确区分。
2. 真实模式分别执行动作1和动作2。
3. 连续运行至少 5 分钟没有误触发。
4. 确认摄像头设备名重启后稳定。

满足以上条件后，按照 `docs/atlas_autostart.md` 安装并验证 systemd 服务。先永久屏蔽串口登录服务并降低运行阶段的内核串口日志，不要直接修改未知来源的启动参数文件。
