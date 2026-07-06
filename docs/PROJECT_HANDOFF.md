# 智元素机器人项目交接说明

本文档用于把当前项目进度交接给同组成员。当前项目已经完成“手机网页控制 + Atlas 部署 + 摄像头模板识别 + 轮询识别触发动作”的原型闭环，后续可以在此基础上继续做更稳定的视觉识别和脱离电脑中转的部署。

## 1. 当前目标

本项目面向智元素格斗机器人，目标是通过手机端网页控制机器人移动，并让 Atlas DK A2 通过摄像头识别标靶任务，然后触发机器人动作。

当前实现的演示流程是：

```text
手机网页控制机器人移动
Atlas 摄像头持续轮询识别任务卡
识别到“位置一 劈砍”
网页语音播报
机器人停车并执行动作 action_id=4
```

注意：当前视觉识别采用“模板识别”作为稳定演示方案，不是通用 OCR。它适合当前固定任务卡和固定标靶样式的阶段。

## 2. 当前项目结构

```text
robot-phone-control/
├─ server/
│  ├─ main.py                 # FastAPI 后端入口，提供网页、WebSocket、摄像头、模板识别接口
│  ├─ robot_adapter.py        # 智元素机器人 UDP 控制协议封装，以及 mock 模式
│  ├─ camera_capture.py       # Atlas/Linux 摄像头拍照，优先使用 fswebcam
│  ├─ template_match.py       # 当前推荐使用的任务卡模板识别
│  ├─ vision_ocr.py           # Tesseract OCR 试验版，保留但当前不作为主路线
│  └─ static/
│     ├─ index.html           # 手机网页控制台
│     ├─ app.js               # 前端控制、识别、轮询逻辑
│     └─ styles.css           # 页面样式
├─ tools/
│  └─ zys_udp_test.py         # Windows/电脑端 UDP 协议测试工具
├─ scripts/
│  ├─ install_atlas.sh        # Atlas 安装 Python 依赖
│  ├─ install_ocr_atlas.sh    # Atlas 安装 OCR 依赖
│  ├─ install_camera_atlas.sh # Atlas 安装摄像头工具
│  ├─ run_atlas.sh            # Atlas 启动脚本
│  ├─ check_atlas_network.sh  # Atlas 网络检查脚本
│  ├─ atlas_enable_ics_keep_ssh.sh # USB 共享网络辅助脚本
│  └─ package_for_atlas.ps1   # Windows 打包 Atlas 部署 zip
├─ docs/
│  ├─ PROJECT_HANDOFF.md      # 本交接文档
│  ├─ beginner_udp_test.md
│  ├─ phone_web_control.md
│  ├─ atlas_beginner_start.md
│  ├─ atlas_no_hdmi_usb_ssh.md
│  └─ atlas_deploy.md
├─ README.md
├─ PROJECT_NOTES.md
└─ requirements.txt
```

## 3. 已经完成的功能

### 3.1 智元素 UDP 控制协议

已根据智元素开放协议实现 UDP 控制，核心文件：

```text
server/robot_adapter.py
tools/zys_udp_test.py
```

已经验证过的能力：

```text
搜索机器人
授权/登录，默认密码 88888888
查询电池
停止
底盘移动
模式切换
动作触发 action_id
```

机器人默认地址：

```text
Robot IP: 192.168.4.1
UDP Port: 9999
Password: 88888888
```

独立测试命令示例：

```bash
python tools/zys_udp_test.py search
python tools/zys_udp_test.py --robot-ip 192.168.4.1 stop
python tools/zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 10 --turn 0 --duration 0.25
python tools/zys_udp_test.py --robot-ip 192.168.4.1 action --action-id 4
```

### 3.2 手机网页控制台

核心文件：

```text
server/static/index.html
server/static/app.js
server/static/styles.css
```

当前网页支持：

```text
前进 / 后退 / 左移 / 右移
左转 / 右转
停止
速度调节
普攻 action_id=4
开机动作 action_id=7
模式0 / 模式2
电池查询
摄像头拍照
模板校准
模板识别并播报
停车识别并执行
开始轮询识别 / 停止轮询
复制日志 / 清空日志
```

### 3.3 Atlas DK A2 部署

已完成 Atlas 无 HDMI 场景下通过 USB RNDIS + MobaXterm 连接。

常用登录方式：

```text
SSH: root@192.168.0.2
默认密码: Mind@123
```

当前项目通常部署在 Atlas：

```text
/root/robot-phone-control
```

启动 mock 模式：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode mock
```

启动真实 UDP 控制模式：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
```

### 3.4 摄像头拍照

核心文件：

```text
server/camera_capture.py
scripts/install_camera_atlas.sh
```

Atlas 上安装摄像头工具：

```bash
cd /root/robot-phone-control
./scripts/install_camera_atlas.sh
```

当前优先通过 `fswebcam` 从 `/dev/video0` 拍照。

### 3.5 任务卡模板识别

核心文件：

```text
server/template_match.py
```

当前稳定路线不是 OCR，而是模板识别：

```text
先拍一张标准任务卡作为模板
保存模板特征到 data/task_templates.json
后续拍照时与模板比较相似度
相似度超过阈值则判定为对应任务
```

默认任务：

```text
位置一 劈砍
```

当前默认动作映射：

```text
位置一 劈砍 -> action_id=4
```

注意：`action_id=4` 当前对应界面上的“普攻”。如果后续确认智元素机器人里真正的“劈砍”对应其它动作编号，需要修改前端 `server/static/app.js` 中调用 `/api/camera/template/execute` 时传入的 `action_id`，或在后端做动作映射表。

### 3.6 轮询识别

核心文件：

```text
server/static/app.js
```

当前轮询逻辑：

```text
点击“开始轮询识别”
前端每 1.2 秒调用 /api/camera/template/recognize
连续 2 次 matched=true 后认为发现任务卡
自动发送 stop
等待约 0.5 秒
调用 /api/camera/template/execute
识别确认成功后执行 action_id=4
```

轮询识别适合答辩演示：

```text
用户只负责遥控机器人移动
系统后台持续识别任务卡
发现任务卡后自动停车、播报、执行动作
```

## 4. 当前推荐演示流程

### 4.1 mock 安全测试

先启动 mock：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode mock
```

浏览器打开：

```text
http://192.168.137.100:8000
```

操作顺序：

```text
1. 摄像头对准任务卡
2. 点击“校准当前任务卡”
3. 点击“模板识别并播报”，确认可识别
4. 点击“开始轮询识别”
5. 将任务卡移入摄像头画面
6. 观察日志 AUTO SCAN / AUTO EXECUTE
```

### 4.2 真实机器人测试

确认机器人已开启并连接网络后启动：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
```

建议先架空轮子或放在安全区域。

操作顺序：

```text
1. 校准当前任务卡
2. 模板识别并播报
3. 开始轮询识别
4. 手动遥控机器人慢速靠近标靶
5. 系统自动停车、播报、执行动作
```

## 5. 当前网络方案

目前主要使用电脑作为中转：

```text
Atlas <-USB/RNDIS-> Windows 电脑 <-WiFi-> 机器人 MYAP
手机可以通过 Windows 端口转发访问 Atlas 服务
```

电脑可以直接访问：

```text
http://192.168.137.100:8000
```

如果手机连接机器人 MYAP 后访问不了 `192.168.137.100:8000`，这是正常的，因为手机和 Atlas 的 USB 网络不在同一网段。

Windows 中转给手机访问时，可以使用管理员 PowerShell：

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=192.168.137.100 connectport=8000
netsh advfirewall firewall add rule name="Atlas Web 8000" dir=in action=allow protocol=TCP localport=8000
```

然后手机访问电脑在机器人 MYAP 下的 WLAN IP，例如：

```text
http://192.168.4.2:8000
```

## 6. 后续摆脱电脑中转：网线/路由器方案

只写开机自启动脚本不能彻底摆脱电脑，因为 Atlas 还需要独立进入机器人所在网络。目前这块 Atlas 没有可用 WiFi，因此推荐使用“小路由器 + 网线”的方案。

### 6.1 推荐网络拓扑

准备一个支持 WISP/无线中继/客户端模式的小路由器或随身路由。

拓扑：

```text
机器人 MYAP 热点
        ^
        | 小路由器 WiFi 客户端连接 MYAP
        |
小路由器 LAN/WiFi
   ├─ Atlas 通过网线连接小路由器 LAN 口
   └─ 手机连接小路由器 WiFi
```

这样：

```text
Atlas 可以通过小路由器访问机器人 192.168.4.1:9999
手机可以通过小路由器访问 Atlas 的 8000 端口
电脑不再参与运行
```

### 6.2 配置步骤

1. 小路由器设置为 WISP/无线客户端/无线中继模式。
2. 小路由器上级 WiFi 选择机器人热点 `MYAP-xxxxxx`。
3. WiFi 密码一般为：

```text
88888888
```

4. Atlas 通过网线接入小路由器 LAN 口。
5. 手机连接小路由器提供的 WiFi，而不是直接连接机器人 MYAP。
6. 在 Atlas 上查看 IP：

```bash
ip addr
ip route
```

假设 Atlas 获得：

```text
192.168.8.100
```

手机访问：

```text
http://192.168.8.100:8000
```

7. 在 Atlas 上确认能访问机器人：

```bash
ping 192.168.4.1
```

如果能 ping 通，就可以启动真实模式：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
```

### 6.3 开机自启动服务

当无电脑网络方案稳定后，可以创建 systemd 服务，让 Atlas 开机自动启动后台。

示例：

```bash
cat >/etc/systemd/system/robot-phone-control.service <<'EOF'
[Unit]
Description=Robot Phone Control Service
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/root/robot-phone-control
ExecStart=/root/robot-phone-control/.venv/bin/python /root/robot-phone-control/server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable robot-phone-control
systemctl start robot-phone-control
systemctl status robot-phone-control
```

如果服务异常，查看日志：

```bash
journalctl -u robot-phone-control -f
```

## 7. 后续开发建议

### 7.1 短期任务

```text
1. 找到“劈砍”真实对应的 action_id
2. 把动作映射从前端硬编码 action_id=4 改为后端映射表
3. 提高模板匹配稳定性，支持多个模板
4. 增加轮询识别的参数配置，例如间隔、连续命中次数、阈值
5. 做一个“演示模式”按钮，一键校准/轮询/停止
```

### 7.2 中期任务

```text
1. 使用二维码或 ArUco 标记替代纯 OCR，提高移动场景稳定性
2. 多任务卡模板识别：位置一/二/三 + 不同动作
3. 任务卡外框检测，自动定位标靶区域
4. 机器人接近标靶后自动停车拍照
```

### 7.3 长期任务

```text
1. 机器人自主寻找标靶
2. 自动绕标靶一周
3. 视觉目标跟踪
4. 更稳定的 OCR/PaddleOCR/分类模型
5. 无电脑开机自启动和手机直连控制
```

## 8. 常见问题

### 手机连机器人热点后打不开 Atlas 页面

原因：手机和 Atlas 不在同一网络。当前电脑中转模式下，手机不能直接访问 `192.168.137.100`。

解决：

```text
使用 Windows portproxy，手机访问电脑 WLAN IP:8000
或使用小路由器/USB WiFi，让 Atlas 和手机进入同一个网络
```

### 模板识别失败

先确认：

```text
1. 已经点击“校准当前任务卡”
2. 摄像头和任务卡距离变化不大
3. 光线稳定，画面不模糊
4. 日志里 template_score 是否低于 threshold
```

可以重新校准当前任务卡。

### 轮询识别误触发或不触发

当前逻辑需要连续 2 次命中才触发。可以后续调整：

```text
轮询间隔：server/static/app.js 中 setInterval(autoScanTick, 1200)
连续命中次数：server/static/app.js 中 autoScanHits < 2
模板阈值：环境变量 TASK_TEMPLATE_THRESHOLD，默认 0.68
```

### Atlas 断电后程序还在吗

代码已经在：

```text
/root/robot-phone-control
```

断电后不会丢失。下次重新 SSH 进入 Atlas 后启动服务即可。

## 9. 交接给组员的最小启动说明

组员拿到代码后，电脑端可先本地启动 mock：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server/main.py --host 0.0.0.0 --port 8000 --robot-mode mock
```

Atlas 上启动：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode mock
```

真实机器人模式：

```bash
cd /root/robot-phone-control
.venv/bin/python server/main.py --host 0.0.0.0 --port 8000 --robot-mode udp --robot-ip 192.168.4.1 --robot-password 88888888
```
