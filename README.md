# Robot Phone Control Starter

手机端控制智元素机器人的最小 starter。

## 当前交接文档

目前项目已经扩展到 Atlas 摄像头、任务卡模板识别、轮询识别和识别后执行动作。完整进度、代码说明、部署方式、无电脑网线/路由器方案见：

```text
docs/PROJECT_HANDOFF.md
```

## 从 MYAP 热点开始测试 UDP 控制

如果你已经让电脑连接到机器人 `MYAP-XXXXXX` 热点，先按照这份新手步骤测试：

```text
docs/beginner_udp_test.md
```

对应脚本：

```bash
python tools/zys_udp_test.py search
python tools/zys_udp_test.py --robot-ip 192.168.4.1 battery
python tools/zys_udp_test.py --robot-ip 192.168.4.1 stop
```

命令行测试成功后，继续按手机网页控制步骤运行：

```text
docs/phone_web_control.md
```

启动 UDP 网页控制服务：

```bash
python server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
```

## 部署到 Atlas DK A2

电脑端网页控制成功后，按这份文档把服务迁移到 Atlas：

```text
docs/atlas_beginner_start.md
docs/atlas_no_hdmi_usb_ssh.md
docs/atlas_deploy.md
```

## OCR 识别与语音播报

网页控制台支持上传图片识别任务文本。Atlas 上需要额外安装 OCR 依赖：

```bash
cd /root/robot-phone-control
chmod +x scripts/*.sh
./scripts/install_ocr_atlas.sh
./scripts/run_atlas.sh
```

## 在机器人上运行 mock 模式

```bash
cd ~/zys_target_task/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
python3 main.py --host 0.0.0.0 --port 8000 --robot-mode mock
```

手机和机器人连接同一个 WiFi 后，在手机浏览器打开：

```text
http://ROBOT_IP:8000
```

## 运行真实机器人模式

先打开官方示例：

```bash
~/up_ele_base_class_code/app/test_control.py
```

把官方示例里的运动、停止、射击、装填调用补到：

```text
server/robot_adapter.py
```

然后运行：

```bash
cd ~/zys_target_task/server
source .venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$HOME/up_ele_base_class_code
python3 main.py --host 0.0.0.0 --port 8000 --robot-mode real
```

