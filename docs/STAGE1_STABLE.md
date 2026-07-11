# 阶段一稳定版

稳定版名称：`stage1-stable-v1.0.0`

## 已完成功能

- Android App通过机器人MYAP热点和UDP协议直接控制底盘。
- Android App提供摇杆连续移动和普攻控制。
- Android App使用本地Google ML Kit识别任务卡。
- Atlas通过USB摄像头持续轮询任务卡。
- Atlas使用RapidOCR离线识别“位置1 劈砍”和“位置2 劈砍”。
- Atlas通过`/dev/ttyAMA0`和机器人UART1透明串口桥执行动作1、动作2。
- 动作1、动作2播放机器人动作文件中保存的对应语音。
- 同一张任务卡持续出现在画面中时只执行一次，移开后重新允许触发。
- `zys-atlas-task-runner.service`随Atlas开机自动启动，不依赖电脑或网络。

## 稳定运行参数

```text
SERIAL_PORT=/dev/ttyAMA0
SERIAL_BAUD=115200
CAMERA=/dev/video0
RECOGNIZER=rapidocr
INTERVAL=0.2
CONFIRM_HITS=1
RAPIDOCR_MIN_CONFIDENCE=0.90
COOLDOWN=10
REARM_MISSES=2
STOP_BEFORE_ACTION=1
```

## 最终系统结构

```text
手机Android App --WiFi/UDP--> 机器人底盘

USB摄像头 --> Atlas RapidOCR --> UART透明桥 --> 机器人动作与语音
```

手机和Atlas互不依赖。电脑只用于安装、升级和查看日志，不参与最终运行。

## Atlas恢复方式

将稳定版部署包上传到Atlas的`/root/robot-phone-control-atlas.zip`，然后执行：

```bash
systemctl stop zys-atlas-task-runner.service 2>/dev/null || true
cd /root/robot-phone-control
unzip -o /root/robot-phone-control-atlas.zip
chmod +x scripts/*.sh
./scripts/install_atlas_autostart.sh
```

检查：

```bash
systemctl is-enabled zys-atlas-task-runner.service
systemctl is-active zys-atlas-task-runner.service
systemctl is-enabled serial-getty@ttyAMA0.service
systemctl is-active serial-getty@ttyAMA0.service
```

预期为：

```text
enabled
active
masked
inactive
```

## Android恢复方式

使用Android Studio打开仓库中的`android-app`目录，连接手机后运行`app`配置。

命令行构建调试APK：

```powershell
cd android-app
.\gradlew.bat assembleDebug
```

APK输出位置：

```text
android-app/app/build/outputs/apk/debug/app-debug.apk
```

## 阶段二隔离规则

- 不覆盖或重命名该Git标签。
- 不修改机器人现有动作文件和`UART1TOUART2`透明桥固件。
- 阶段二使用独立分支、独立目录和独立systemd服务。
- 阶段一与阶段二服务不得同时打开摄像头和`/dev/ttyAMA0`。
- 阶段二失败时，停用阶段二服务并重新启用`zys-atlas-task-runner.service`。
