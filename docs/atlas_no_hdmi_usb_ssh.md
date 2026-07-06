# Atlas DK A2 无 HDMI：用 Windows 电脑远程操作

这份文档适合你现在的情况：没有 HDMI 显示器和线，希望直接用 Windows 电脑操作 Atlas。

核心思路：

```text
Windows 电脑
  -- Type-C 数据线 --
Atlas DK A2

Windows 把 Atlas 识别成 USB RNDIS 虚拟网卡
Windows 通过 SSH 登录 Atlas
你在 Windows 上输入命令，但命令实际运行在 Atlas 里
```

根据你提供的《Atlas200I DK A2环境搭建指南.docx》：

- Atlas USB 默认 IP：`192.168.0.2`
- 远程 SSH 用户：`root`
- 默认密码：`Mind@123`

如果你的镜像或课程资料给了不同账号密码，以你的资料为准。

## 0. 准备

需要：

- Atlas DK A2
- 已烧录好的 SD 卡
- Atlas 电源
- 支持数据传输的 Type-C 线
- Windows 电脑
- MobaXterm，或者 Windows 自带 PowerShell SSH

注意：Type-C 线必须是数据线，不是只能充电的线。

## 1. Atlas 插入 SD 卡并上电

1. 把 SD 卡插入 Atlas 的 SD 卡槽，确保插到底。
2. 检查拨码开关 2、3、4 是否符合环境搭建指南里的启动图示。
3. 用 Type-C 数据线连接 Atlas Type-C 接口和 Windows 电脑。
4. 接 Atlas 电源，上电。
5. 等待 1-3 分钟。

首次启动可能会自动升级固件并重启。第一次请多等一会儿，不要 1 分钟内断电。

## 2. Windows 检查 USB RNDIS 虚拟网卡

在 Windows 上：

1. 右键“开始菜单”。
2. 打开“设备管理器”。
3. 找到是否出现：

```text
RNDIS
USB RNDIS
USB Ethernet/RNDIS Gadget
```

如果它在“网络适配器”里，通常已经可用。

如果它有黄色感叹号：

1. 右键该设备。
2. 选择“更新驱动程序”。
3. 选择“浏览我的电脑以查找驱动程序”。
4. 选择“让我从计算机上的可用驱动程序列表中选取”。
5. 找到“网络适配器”。
6. 厂商选择 `Microsoft`。
7. 型号选择 `USB RNDIS6 适配器`。
8. 下一步，完成安装。

## 3. 配置 Windows 端 USB 网卡 IP

Atlas USB 默认 IP 是：

```text
192.168.0.2
```

所以 Windows 的 USB RNDIS 网卡要设置成同一网段，比如：

```text
IP 地址：192.168.0.1
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

操作步骤：

1. 打开 Windows 设置。
2. 进入“网络和 Internet”。
3. 找到“高级网络设置”。
4. 打开“更多网络适配器选项”。
5. 找到 `USB RNDIS6 适配器`。
6. 右键 -> 属性。
7. 双击 `Internet 协议版本 4 (TCP/IPv4)`。
8. 选择“使用下面的 IP 地址”。
9. 填入：

```text
IP 地址：192.168.0.1
子网掩码：255.255.255.0
默认网关：空
```

保存。

## 4. 测试 Windows 能否 ping 到 Atlas

打开 Windows PowerShell，执行：

```powershell
ping 192.168.0.2
```

如果看到类似：

```text
来自 192.168.0.2 的回复
```

说明 Windows 已经能连到 Atlas。

如果 ping 不通：

- 确认 Atlas 已上电并等待足够久。
- 确认 Type-C 线是数据线。
- 确认 RNDIS 驱动正常。
- 确认 Windows USB RNDIS 网卡 IP 是 `192.168.0.1`。
- 临时关闭 Windows 防火墙再试一次。

## 5. 用 PowerShell SSH 登录 Atlas

PowerShell 执行：

```powershell
ssh root@192.168.0.2
```

第一次会问：

```text
Are you sure you want to continue connecting?
```

输入：

```text
yes
```

然后输入密码：

```text
Mind@123
```

注意：Linux 输入密码时屏幕不会显示星号，这是正常的。输入完直接按回车。

登录成功后，你会看到类似：

```bash
root@atlas:~#
```

此时你已经在 Atlas 命令行里了。

如果你看到类似：

```bash
(base) root@davinci-mini:~#
```

也表示已经登录成功。`base` 只是系统自动进入了一个 Python/conda 环境。

## 6. 用 MobaXterm 登录 Atlas

如果你不想用 PowerShell，也可以用 MobaXterm：

1. 打开 MobaXterm。
2. 点击 `Session`。
3. 选择 `SSH`。
4. Remote host 填：

```text
192.168.0.2
```

5. Port 填：

```text
22
```

6. 勾选 specify username，填：

```text
root
```

7. 连接后输入密码：

```text
Mind@123
```

## 7. 登录后先执行基础检查

在 Atlas SSH 终端里执行：

```bash
uname -a
python3 --version
ip -4 addr
pwd
```

把这些输出发给我，我可以继续判断你的系统状态。

## 8. 让 Atlas 通过 Windows 共享网络上网

安装 Python 依赖需要 Atlas 能上网。无 HDMI 情况下，常用办法是让 Windows 通过 Type-C 虚拟网卡给 Atlas 共享网络。

注意：这一步会把连接地址从 `192.168.0.2` 改到 `192.168.137.100`。如果你不熟悉 Linux 网络配置，先把下面命令输出发给我，我帮你看了再改：

```bash
cat /etc/netplan/01-netcfg.yaml
ip -4 addr
```

环境搭建指南里的思路是：

1. 先 SSH 登录 `192.168.0.2`。
2. 修改 Atlas 的 USB 网卡 `usb0` 到 `192.168.137.x` 网段。
3. Windows 开启 Internet 连接共享。
4. Windows RNDIS 网卡变成 `192.168.137.1`。
5. 之后用 `192.168.137.100` 重新登录 Atlas。

Windows 共享网络路径：

1. 打开“网络连接”。
2. 找到当前能上网的网卡，比如 WiFi 或以太网。
3. 右键 -> 属性。
4. 打开“共享”选项卡。
5. 勾选“允许其他网络用户通过此计算机的 Internet 连接来连接”。
6. 家庭网络连接选择 `USB RNDIS6 适配器`。
7. 确定。

之后 Windows 的 USB RNDIS 网卡通常会变成：

```text
192.168.137.1
```

你需要重新 SSH：

```powershell
ssh root@192.168.137.100
```

确认联网：

```bash
ping -c 2 pypi.org
```

### 更稳的共享网络配置：保留 SSH 地址

如果 `ip -4 addr` 显示 Atlas 当前是：

```text
usb0 192.168.0.2/24
```

不要清空 `usb0`，否则 SSH 可能断开。先在 Windows 上打开网络共享，让 USB RNDIS 网卡同时有：

```text
192.168.0.1
192.168.137.1
```

然后在当前 SSH 会话中执行：

```bash
ip addr add 192.168.137.100/24 dev usb0
ip link set usb0 up
ip route replace default via 192.168.137.1 dev usb0
resolvectl dns usb0 223.5.5.5 8.8.8.8
```

这样会保留 `192.168.0.2`，当前 SSH 通常不会断开。测试：

```bash
ping -c 2 192.168.137.1
ping -c 2 223.5.5.5
ping -c 2 pypi.org
```

## 9. 你现在先做到哪一步

请先完成：

```powershell
ping 192.168.0.2
ssh root@192.168.0.2
```

登录成功后，在 Atlas 里执行：

```bash
uname -a
python3 --version
ip -4 addr
cat /etc/netplan/01-netcfg.yaml
```

把输出发给我。下一步我会带你配置 Windows 共享网络，然后安装并运行机器人控制服务。
