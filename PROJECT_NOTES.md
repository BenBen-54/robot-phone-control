# 智元素机器人项目进度

## 当前稳定基线

当前稳定版本：`stage1-stable-v1.0.0`

完整恢复说明见：`docs/STAGE1_STABLE.md`。

## 阶段一已完成

### Android直接控制

- 手机连接机器人MYAP热点。
- Android App直接通过UDP协议控制机器人，不依赖Atlas或电脑中转。
- 摇杆以固定周期发送移动指令，支持连续平滑移动。
- App保留普攻动作。
- App内置Google ML Kit中文OCR，可识别位置1/位置2任务卡。

### Atlas独立视觉与动作

- Atlas 200I DK A2连接USB摄像头。
- RapidOCR和ONNX Runtime部署在Atlas本地，运行时不访问云端API。
- Atlas通过40Pin `/dev/ttyAMA0`、115200波特率连接机器人UART1。
- 机器人中的Arduino Mega运行`UART1TOUART2`透明串口转发程序。
- 串口使用机器人背包协议`F5 5F`帧，不使用WiFi协议的`FE EF`帧。
- 位置1执行动作1，位置2执行动作2，动作文件中包含对应语音。
- 同一任务卡只触发一次，移开后重新允许触发。

### 无电脑运行

- `zys-atlas-task-runner.service`开机自动启动。
- `serial-getty@ttyAMA0.service`已屏蔽，串口由Python服务独占。
- 稳定参数为单帧确认和最低0.90 OCR置信度。
- 手机继续直接控制机器人底盘，Atlas独立完成OCR和动作。

## 阶段一关键文件

```text
android-app/                         Android手机App
server/rapidocr_recognizer.py       Atlas RapidOCR识别器
server/atlas_task_runner.py         轮询、确认、冷却和动作状态逻辑
server/robot_adapter.py             UDP与UART机器人适配器
server/task_actions.py              任务到动作编号映射
tools/zys_serial_test.py            串口诊断工具
systemd/zys-atlas-task-runner.service
scripts/install_atlas_autostart.sh
docs/STAGE1_STABLE.md
```

## 阶段二目标

阶段二计划在独立分支和服务中实现：

```text
目标检测柱子
-> 接近并环绕柱子
-> 定位任务纸
-> RapidOCR读取任务
-> 目标检测锣
-> 接近并对准锣
-> 执行对应劈砍动作
```

推荐使用轻量YOLO模型，在电脑端训练并导出ONNX，再转换为Atlas Ascend310B4使用的OM模型。阶段二必须保留以下隔离规则：

- 不修改或覆盖阶段一稳定标签。
- 不覆盖机器人动作文件和UART透明桥固件。
- 阶段二使用独立systemd服务。
- 两个服务不得同时占用摄像头和`/dev/ttyAMA0`。
- 阶段二失败时能够立即重新启用阶段一服务。
