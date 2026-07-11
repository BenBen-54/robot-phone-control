# Atlas 通过 UART 控制智元素机器人：第一步安全测试

这一步只验证一件事：Atlas 能否通过提供的绿色转接板和机器人 `UART1` 接口，触发动作1或动作2。

暂时不安装 OCR，不连接 USB 摄像头，不测试底盘前进。串口验证成功后，再继续做摄像头和本地 OCR。

## 1. 当前架构

```text
手机 Android App -- MYAP Wi-Fi / UDP --> 机器人底盘

USB 摄像头 -- USB --> Atlas -- UART --> 机器人动作1/动作2
```

Atlas 运行时不需要 Wi-Fi 网卡。开发和上传文件时，继续使用电脑与 Atlas 之间已经验证过的 USB-RNDIS SSH。

## 必做前置步骤：给机器人烧录串口转发程序

机器人出厂状态下，`UART1` 接口不会自动把 Atlas 发来的数据转交给内部控制系统。根据《智元素使用指导书》的“背包 Python 趣味案例”章节，在使用外部计算板控制机器人之前，必须先把老师提供的 `UART1TOUART2.ino` 烧录到机器人的 Arduino 控制器。

该程序将 `Serial1` 和 `Serial2` 都设置为 `115200`，并在两个串口之间逐字节透明转发。没有完成这一步时，即使 Atlas 串口、协议包和接线均正确，机器人也可能完全没有回包和动作。

烧录会覆盖机器人当前运行的 Arduino 草图。如果机器人中曾经烧录过需要保留的自定义 Arduino 程序，应先保存其源代码。该操作通常不会删除动作编辑器写入的 `.MFO` 动作文件，但烧录前仍应保留动作文件备份。

烧录完成并重新启动机器人后，再继续下面的 Atlas 串口测试。串口波特率固定先使用 `115200`，不要把 Wi-Fi 模块内部使用的 `921600` 当作外部 `UART1` 的首选波特率。

厂家《智元素-格斗机器人功能函数参考文档》明确说明，标准 Arduino IDE 用户选择 `Arduino/Genuino Mega or Mega 2560`，处理器选择 `ATmega2560 (Mega 2560)`，端口选择实际出现的 `COMx`。`UART1TOUART2.ino` 使用了 Mega 2560 提供的 `Serial1` 和 `Serial2`，不能选择 Uno。`WisdomElement.zip` 是机器人函数库，不是板卡定义；这个透明转发程序本身没有引用该库，因此烧录它不要求先安装该库。正常上传不需要更改“编程器”，也不要点击“烧录引导程序”。

现有机器人手册没有标注外部可见的 `RX/TX` 指示灯，也没有标注可操作的 `RESET/RST` 按钮。手册中的“机器人功能键”不是 Arduino 复位键；按住该键开机进入的是 USB U 盘模式，不能用它替代上传复位。若标准 Mega 2560 配置持续出现 `stk500v2_getsync()` 超时，应停止反复抢开机时机，向厂家或教师确认该批次机器人的下载复位方法，并检查 USB-串口自动复位线路或 Bootloader 状态。不要自行烧录 Bootloader。

厂家 `WisdomElement` 库还确认了 Arduino/背包侧控制帧使用 `F5 5F` 帧头，而不是手机 Wi-Fi/UDP 使用的 `FE EF` 完整帧。Atlas 串口测试工具默认采用 `bridge` 模式生成 `F5 5F` 帧；只有复现 Wi-Fi 模块内部协议时才显式使用 `--protocol wifi`。

## 2. 协议核对结果

- 控制包帧头为 `FE EF`。
- 动作命令为设备 `0x07`、命令 `0x55`。
- `action_id=0` 对应动作1，`action_id=1` 对应动作2，`action_id=4` 对应普攻。
- 开放协议中的 `921600` 是 Wi-Fi 模块内部链路信息，不代表机器人外部 `UART1` 接口应使用该速率。
- 老师提供的 `UART1TOUART2.ino` 对两个外部 UART 都使用 `115200`，并逐字节透明转发。

因此，烧录转发程序后的外部 UART 测试使用 `115200`。在没有厂家或老师进一步确认的情况下，不再盲目切换到 `921600`。

## 3. 接线前安全准备

1. 将机器人放在宽敞桌面或支架上，确保手臂和武器周围没有人和物品。
2. 关闭官方手机 App、动作编辑器和我们自己的 Android App。
3. 关闭机器人电源。
4. 在 Atlas 的 MobaXterm 终端执行：

   ```bash
   poweroff
   ```

5. 等 Atlas 完全关机后再接线。
6. 使用老师提供的绿色转接板和原配水晶头线，将转接板接口接到机器人标记为 `UART1` 的接口。
7. 不自行增加 5V 跳线，不把机器人 5V 接到其它 Atlas GPIO。Atlas 继续使用自己的电源，机器人使用自己的电池。
8. 确认插头方向和转接板安装方向与老师给出的实物一致，然后再分别上电。

## 4. 在 Windows 上生成 Atlas 压缩包

以下命令在 **Windows PowerShell** 执行，不是在 MobaXterm 的 Atlas 终端执行。

```powershell
cd C:\Users\20914\Documents\robot-phone-control
powershell -ExecutionPolicy Bypass -File .\scripts\package_for_atlas.ps1
```

成功后会生成：

```text
C:\Users\20914\Documents\robot-phone-control\dist\robot-phone-control-atlas.zip
```

## 5. 用 MobaXterm 上传代码

1. 电脑通过 USB 管理线连接 Atlas。
2. 打开以前保存的 MobaXterm SSH 会话，优先连接 `root@192.168.137.100`。
3. 如果该地址不通，先在 Windows PowerShell 测试：

   ```powershell
   ping 192.168.137.100
   ping 192.168.0.2
   ```

4. SSH 成功后，MobaXterm 左侧会出现 `/root` 文件列表。
5. 将刚生成的 `robot-phone-control-atlas.zip` 上传到 `/root/`。

## 6. 在 Atlas 上更新项目

下面开始，命令全部在 **MobaXterm 黑色 Atlas 终端** 中执行。提示符应类似：

```text
(base) root@davinci-mini:~#
```

执行：

```bash
cd /root
unzip -o robot-phone-control-atlas.zip -d robot-phone-control
cd /root/robot-phone-control
```

不要删除整个项目目录，`unzip -o` 只覆盖本次压缩包中更新过的文件。

## 7. 安装并检查 pyserial

先检查项目虚拟环境是否存在：

```bash
cd /root/robot-phone-control
ls -l .venv/bin/python
```

如果能看到文件，执行：

```bash
.venv/bin/python -m pip install pyserial==3.5
.venv/bin/python -c "import serial; print(serial.__version__)"
```

最后一条命令预期输出：

```text
3.5
```

如果提示 `.venv/bin/python` 不存在，执行：

```bash
cd /root/robot-phone-control
python3 -m venv .venv
.venv/bin/python -m pip install pyserial==3.5
```

安装依赖只在开发阶段需要电脑共享网络；安装完成后，运行串口程序不需要互联网。

## 8. 识别 Atlas 串口设备名

先运行项目提供的端口枚举命令：

```bash
cd /root/robot-phone-control
.venv/bin/python tools/zys_serial_test.py ports
```

再运行 Linux 原始检查命令：

```bash
ls -l /dev/ttyAMA* /dev/ttyS* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

常见候选名称包括：

```text
/dev/ttyAMA0
/dev/ttyAMA1
/dev/ttyS0
/dev/ttyUSB0
/dev/ttyACM0
```

不要直接猜设备名。先记录实际输出。绿色 40 针转接板通常对应硬件 UART，因此即使没有 `/dev/ttyUSB0` 也不代表失败。

## 9. 检查串口是否被系统控制台占用

假设上一步的候选端口是 `/dev/ttyAMA0`，执行：

```bash
systemctl status serial-getty@ttyAMA0.service --no-pager
fuser -v /dev/ttyAMA0
```

如果服务显示 `active (running)`，先停止它：

```bash
systemctl disable --now serial-getty@ttyAMA0.service
```

如果候选端口不是 `/dev/ttyAMA0`，把以上命令中的名称替换为实际名称。

不要停止 USB-RNDIS、SSH 或网络相关服务。

## 10. 第一次只监听，不发送数据

仍以 `/dev/ttyAMA0` 为例：

```bash
cd /root/robot-phone-control
.venv/bin/python tools/zys_serial_test.py --port /dev/ttyAMA0 --baud 115200 listen --seconds 5
```

这个命令不会控制机器人。没有收到数据也不一定是错误，因为机器人可能只在收到查询后才回包。

## 11. 授权和只读探测

关闭官方 App 和动作编辑器，确保机器人已正常开机，然后执行：

```bash
.venv/bin/python tools/zys_serial_test.py --port /dev/ttyAMA0 --baud 115200 probe
```

该命令依次发送：

1. 密码 `88888888` 的授权包。
2. 查询授权状态。
3. 查询电池。

它不会发送动作，也不会移动底盘。

如果完全没有回包，先不要执行动作。依次排查：

1. 设备名是否正确。
2. 动作编辑器和官方 App 是否完全关闭。
3. 绿色转接板与机器人 `UART1` 是否插牢。
4. 是否有系统串口控制台占用。
5. 对同一端口尝试内部协议标出的波特率：

   ```bash
   .venv/bin/python tools/zys_serial_test.py --port /dev/ttyAMA0 --baud 921600 probe
   ```

不要同时修改设备名、接线和波特率，否则无法判断是哪一项起作用。

## 12. 明确确认后测试动作1

只有在机器人上半身周围安全、动作文件已正确写入，并且前面步骤没有串口打开错误时，才执行：

```bash
.venv/bin/python tools/zys_serial_test.py --port /dev/ttyAMA0 --baud 115200 action 0 --confirm
```

预期：机器人执行动作1，并播放为动作1配置的语音。

然后测试动作2：

```bash
.venv/bin/python tools/zys_serial_test.py --port /dev/ttyAMA0 --baud 115200 action 1 --confirm
```

预期：机器人执行动作2，并播放为动作2配置的语音。

部分动作命令可能不回包。只要机器人实际执行了动作，串口发送就已经成功。

## 13. 暂时不要做的事情

- 不要测试串口底盘前进。
- 不要让官方 App、动作编辑器、Android App 和串口脚本同时控制机器人。
- 不要反复插拔带电的 UART 接口。
- 不要在端口不确定时尝试多个 `/dev/tty*` 设备发送动作。
- 不要执行固件升级、Bootloader 或格式化操作。

## 14. 成功标准和下一步

满足以下两项就可以继续 OCR：

1. Atlas 能打开确定的串口设备。
2. `action 0` 和 `action 1` 至少有一个能让机器人实际执行对应动作。

下一步将在 Atlas 上验证 USB 摄像头 `/dev/video0`，然后部署本地 OCR 模型、连续帧确认和动作冷却逻辑。
