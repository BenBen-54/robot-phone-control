# 智元素机器人 UDP 控制新手测试步骤

这份文档从“电脑已经连接到 `MYAP-XXXXXX` 热点”开始。目标不是马上做完整 APP，而是先确认电脑能通过 UDP 协议让机器人响应。

## 0. 安全准备

第一次测试请这样放置机器人：

- 把机器人放在空旷地面，或者把底盘轮子架空。
- 让手远离轮子、手臂和武器。
- 关闭官方手机 APP、动作编辑器、其他控制程序。
- 先不要测试高速移动。

本项目的测试脚本已经做了保护：`move` 命令会限制速度，并且最多运行 1 秒后自动停止。

## 1. 确认电脑已经连上机器人热点

Windows 右下角 WiFi 连接到：

```text
MYAP-XXXXXX
```

默认密码：

```text
88888888
```

然后打开 PowerShell，执行：

```powershell
ipconfig
```

在“无线局域网适配器 WLAN”附近找 IPv4 地址。AP 模式下常见地址是：

```text
192.168.4.2
```

机器人自身常见地址通常可以先试：

```text
192.168.4.1
```

## 2. 进入项目目录

PowerShell 执行：

```powershell
cd C:\Users\20914\Documents\robot-phone-control
```

如果你电脑已经安装了 Python，可以执行：

```powershell
python --version
```

如果提示找不到 Python，可以先用 Codex 自带的 Python 路径：

```powershell
& "C:\Users\20914\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" --version
```

下面的示例先用系统 `python` 写；如果你的系统没有 Python，就把 `python` 换成上面那段完整路径。

## 3. 先只打印协议包，不连接机器人

```powershell
python tools\zys_udp_test.py packets
```

你会看到类似：

```text
搜索机器人: FE EF ...
授权 88888888: FE EF ...
停止: FE EF ...
```

这一步只是确认脚本能运行。

## 4. 搜索机器人

```powershell
python tools\zys_udp_test.py search
```

第一次运行 Python 网络程序时，Windows 可能弹出防火墙提示。请选择允许“专用网络”访问。

如果成功，可能看到：

```text
[发现] 机器人 IP 可能是：192.168.4.1
```

如果没有收到回包，不一定代表失败。你可以继续用默认地址 `192.168.4.1` 做后面的测试。

## 5. 授权机器人

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 auth
```

默认密码是 `88888888`。如果你的机器人密码改过：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 --password 你的密码 auth
```

注意：协议里写了超过 5 秒没有通信，机器人会清除授权。所以后面的命令脚本都会先自动授权一次。

## 6. 查询电池

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 battery
```

如果收到电池数据，会打印：

```text
[电池] 剩余 xx%  电压 xxxx mV  电流 xxxx mA
```

如果没有电池数据，但发送没有报错，可以继续先测试停止命令。

## 7. 发送停止命令

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 stop
```

这条命令很重要。以后只要你觉得机器人状态不对，优先运行这条。

## 8. 第一次低速移动测试

请先把机器人轮子架空，或者放在很空的地方。

前进 0.25 秒：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 10 --turn 0 --duration 0.25
```

后退 0.25 秒：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 180 --speed 10 --turn 0 --duration 0.25
```

左移 0.25 秒：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 90 --speed 10 --turn 0 --duration 0.25
```

右移 0.25 秒：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 270 --speed 10 --turn 0 --duration 0.25
```

原地左转：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 0 --turn 150 --duration 0.25
```

原地右转：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 0 --turn -150 --duration 0.25
```

## 9. 测试动作

先测试“普攻”：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 action 4
```

动作编号：

```text
0-3: 动作 1-4
4: 普攻
5: 失败动作
6: 胜利动作
7: 开机动作
8: 战斗开始动作
```

## 10. 常见问题

如果提示绑定 UDP 9999 失败：

- 关闭官方 APP、动作编辑器、其他 Python 脚本。
- 重新打开 PowerShell。
- 再运行命令。

如果搜索不到机器人：

- 确认电脑 WiFi 还连着 `MYAP-XXXXXX`。
- 运行 `ipconfig`，确认无线网卡是 `192.168.4.x`。
- 直接加 `--robot-ip 192.168.4.1` 测试。

如果命令发出但机器人不动：

- 先用官方 APP 确认机器人本身能动。
- 确认机器人没有处于低电量或异常状态。
- 先运行诊断命令：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 diag
```

- 再运行 `stop`，然后设置底盘模式为 `0`：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 stop
python tools\zys_udp_test.py --robot-ip 192.168.4.1 mode 0
```

- 再测试低速 `move`。
- 如果仍然不动，再测试 `mode 2`：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 mode 2
python tools\zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 10 --turn 0 --duration 0.25
```

- 如果普通 `move` 不动，试一次定时移动：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 timed-move --angle 0 --speed 10 --turn 0 --runtime-ms 300
```

诊断输出里如果授权返回 `params=01`，说明密码正确、UDP 通信已经通了。`stop` / `move` 没有回包不一定表示失败，因为这类运动命令默认不要求响应。

如果查询电池返回全 0，例如：

```text
params=00 00 00 00 00 00 00 00 00 00
```

优先检查底盘和机身连接、电池、机器人是否处于异常状态，并用官方 APP 验证底盘能否运动。

如果机器人持续移动：

立刻执行：

```powershell
python tools\zys_udp_test.py --robot-ip 192.168.4.1 stop
```

必要时直接关闭机器人电源。
