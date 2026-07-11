# Atlas OCR 串口服务开机自启动

本文适用于以下功能已经验证成功的状态：

- RapidOCR 能稳定区分“位置1 劈砍”和“位置2 劈砍”。
- `/dev/video0` 是 USB 摄像头。
- `/dev/ttyAMA0`、115200 波特率能够触发动作1和动作2。
- 程序目录是 `/root/robot-phone-control`。
- 单帧确认，RapidOCR最低置信度为0.90。

## 1. 安装前停止手动程序

在当前运行任务循环的 MobaXterm 终端按 `Ctrl+C`，然后执行：

```bash
fuser -v /dev/ttyAMA0
```

如果只显示 `agetty`，安装脚本会自动停止它。如果显示 `python`，说明手动任务循环仍未结束。

## 2. 安装服务

```bash
cd /root/robot-phone-control
chmod +x scripts/*.sh
./scripts/install_atlas_autostart.sh
```

成功后应看到：

```text
Active: active (running)
```

查看实时日志：

```bash
journalctl -u zys-atlas-task-runner.service -f
```

按 `Ctrl+C` 只会退出日志查看，不会停止后台服务。

## 3. 不重启先验证一次

分别展示两张任务卡，确认日志中出现：

```text
confirmed phrase=位置1 劈砍 action_id=0
confirmed phrase=位置2 劈砍 action_id=1
```

服务控制命令：

```bash
systemctl status zys-atlas-task-runner.service --no-pager
systemctl restart zys-atlas-task-runner.service
systemctl stop zys-atlas-task-runner.service
systemctl start zys-atlas-task-runner.service
```

## 4. 重启验证

```bash
sync
reboot
```

SSH 会立刻断开。等待 Atlas 启动约 2 分钟后，无需先登录，直接给摄像头展示任务卡。机器人能够识别并执行动作，说明开机自启动成功。

重新登录后检查：

```bash
systemctl is-enabled zys-atlas-task-runner.service
systemctl is-active zys-atlas-task-runner.service
systemctl is-enabled serial-getty@ttyAMA0.service
systemctl is-active serial-getty@ttyAMA0.service
journalctl -u zys-atlas-task-runner.service -b -n 80 --no-pager
```

预期依次包含：

```text
enabled
active
masked
inactive
```

此时执行下面命令通常会看到 Python 进程占用串口，这是正确结果，因为任务服务已经成为串口的唯一使用者：

```bash
fuser -v /dev/ttyAMA0
```

## 5. 网络地址说明

任务服务完全不依赖电脑和网络。手机继续连接机器人热点并直接控制底盘，Atlas 独立完成摄像头 OCR 和串口动作。

重启后，临时设置的 `192.168.137.100` 可能消失，Atlas USB 地址通常恢复为 `192.168.0.2`。这只影响 SSH 调试，不影响识别和动作。

## 6. 暂停自启动

```bash
cd /root/robot-phone-control
./scripts/disable_atlas_autostart.sh
```

恢复运行：

```bash
systemctl enable --now zys-atlas-task-runner.service
```

## 7. 关于内核串口控制台

安装脚本会永久屏蔽 `serial-getty@ttyAMA0.service`，并通过 `/etc/sysctl.d/99-zys-uart-console.conf` 抑制系统运行阶段的内核消息。这样能够复现已经验证成功的 `systemctl stop` 加 `dmesg -n 1` 配置，并在每次开机自动生效。

`/proc/cmdline` 中可能仍有 `console=ttyAMA0,115200`，因此非常早期的开机日志仍可能经过 UART0。不要在不知道启动配置来源时直接修改 `/proc/cmdline` 或 `/boot` 文件。如果机器人在 Atlas 启动阶段出现异常动作，再执行以下命令并根据实际文件位置处理：

```bash
cat /proc/cmdline
grep -Rns "console=ttyAMA0" /boot /etc/default 2>/dev/null
```

修改启动参数前必须备份对应文件，并保留 USB SSH 恢复方式。
