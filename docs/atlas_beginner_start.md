# Atlas DK A2 从开机到命令行新手指南

这份文档假设你是第一次使用 Atlas。先把 Atlas 当成一台小型 Linux 电脑理解：

```text
Atlas = 一台运行 Linux 的小电脑
你需要先进入它的终端
然后在终端里安装依赖、运行 Python 服务
```

## 0. 你需要准备什么

如果你没有 HDMI 显示器和线，可以走“Type-C + Windows SSH”的无显示器路线，先看：

```text
docs/atlas_no_hdmi_usb_ssh.md
```

如果你有 HDMI 显示器、键鼠，再继续阅读本文。

建议先准备：

- Atlas DK A2
- Atlas 原装电源或符合要求的电源
- HDMI 显示器
- HDMI 线
- USB 键盘
- USB 鼠标
- 网线，或者 Atlas 可用的 WiFi
- 你的机器人
- 你的手机

第一次使用时，最推荐：

```text
显示器 + 键盘 + 鼠标直连 Atlas
```

这样最直观，不需要一开始就理解 SSH、串口、IP 地址。

## 1. Atlas 开机

1. 先不要连接机器人。
2. 把 HDMI 显示器接到 Atlas。
3. 把 USB 键盘、鼠标接到 Atlas。
4. 接上网线，或者准备稍后连接 WiFi。
5. 最后接 Atlas 电源。
6. 等待 1-3 分钟。

如果显示器出现 Linux 桌面或登录界面，说明开机成功。

如果显示器黑屏：

- 检查 HDMI 线。
- 检查显示器输入源是否选择到正确 HDMI。
- 等待更久一点，首次启动可能比较慢。
- 检查电源指示灯和风扇/散热状态。

## 2. 登录 Atlas

Atlas 出厂镜像不同，默认用户名和密码可能不同。

如果你有卖家/课程资料，以资料为准。

常见情况可能是：

```text
用户名：HwHiAiUser / root / atlas / ascend / ubuntu
密码：与镜像说明一致
```

如果你不知道用户名密码，请先看：

- Atlas 随机资料
- 镜像烧录说明
- 卖家给你的账号说明

如果已经能进入桌面，就继续下一步。

## 3. 打开终端

进入桌面后，打开终端的方法一般有两种：

### 方法 A：快捷键

按：

```text
Ctrl + Alt + T
```

### 方法 B：应用菜单

点击左下角或左上角应用菜单，搜索：

```text
Terminal
终端
```

打开后，你会看到类似：

```bash
用户名@主机名:~$
```

这就是 Atlas 的命令行。

注意：以后我让你在 Atlas 上执行的命令，都要输入到这个终端里，不是在 Windows PowerShell 里。

## 4. 在 Atlas 终端里做第一次检查

依次输入：

```bash
uname -a
```

```bash
python3 --version
```

```bash
pwd
```

```bash
ip -4 addr
```

你应该能看到：

- Linux 系统信息
- Python 版本
- 当前目录，通常是 `/home/某个用户名`
- 网络地址信息

如果这些命令能正常输出，说明你已经进入 Atlas 命令行。

## 5. 让 Atlas 先连接互联网

部署服务前，需要先安装 Python 依赖，所以 Atlas 需要先能上网。

### 方式 A：网线

把 Atlas 用网线接到路由器。

然后执行：

```bash
ping -c 2 pypi.org
```

如果看到类似：

```text
2 received
```

说明能上网。

### 方式 B：WiFi

如果 Atlas 有桌面 WiFi 图标：

1. 点击 WiFi 图标。
2. 选择你家里/实验室 WiFi。
3. 输入 WiFi 密码。
4. 连接成功后执行：

```bash
ping -c 2 pypi.org
```

### 方式 C：命令行 WiFi

如果没有桌面 WiFi 图标，可以试：

```bash
nmcli dev wifi list
```

连接普通 WiFi：

```bash
nmcli dev wifi connect "你的WiFi名称" password "你的WiFi密码"
```

再测试：

```bash
ping -c 2 pypi.org
```

## 6. 什么时候需要连接电脑

“连接电脑”有两种意思：

### 情况 A：电脑只是用来复制项目文件

最简单方式是 U 盘复制。

在 Windows 电脑上复制项目目录到 U 盘，然后插到 Atlas，把文件复制到：

```bash
~/robot-phone-control
```

### 情况 B：电脑远程登录 Atlas

这叫 SSH。它需要电脑和 Atlas 在同一个网络里。

先在 Atlas 上查 IP：

```bash
ip -4 addr
```

找到类似：

```text
192.168.x.x
```

然后在 Windows PowerShell 里执行：

```powershell
ssh 用户名@Atlas_IP
```

例如：

```powershell
ssh HwHiAiUser@192.168.1.23
```

第一次建议你先不用 SSH，先用显示器键盘鼠标直接操作 Atlas。等服务跑通后再学 SSH。

## 7. 把项目放到 Atlas

在 Atlas 终端里，目标目录建议是：

```bash
~/robot-phone-control
```

如果用 U 盘复制，复制完成后执行：

```bash
cd ~/robot-phone-control
ls
```

你应该看到：

```text
server
tools
docs
scripts
requirements.txt
README.md
```

如果看不到这些文件，说明项目没有放对位置。

## 8. 安装项目依赖

保持 Atlas 仍然连接互联网。

执行：

```bash
cd ~/robot-phone-control
chmod +x scripts/*.sh
./scripts/install_atlas.sh
```

如果提示没有 `python3-venv`，执行：

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
./scripts/install_atlas.sh
```

安装成功后，会出现：

```text
Atlas install complete.
Next: ./scripts/run_atlas.sh
```

## 9. Atlas 连接机器人热点

安装依赖完成后，再把 Atlas 的网络切到机器人热点：

```text
MYAP-XXXXXX
密码 88888888
```

如果用桌面 WiFi 图标，就直接选择 `MYAP-XXXXXX`。

如果用命令行：

```bash
nmcli dev wifi list
```

```bash
nmcli dev wifi connect "MYAP-XXXXXX" password "88888888"
```

确认 Atlas 拿到机器人热点里的 IP：

```bash
ip -4 addr
```

你应该能看到类似：

```text
192.168.4.2
```

确认能连到机器人：

```bash
ping -c 2 192.168.4.1
```

## 10. 在 Atlas 上启动控制服务

执行：

```bash
cd ~/robot-phone-control
./scripts/run_atlas.sh
```

看到：

```text
Uvicorn running on http://0.0.0.0:8000
```

说明服务已经启动。

这个终端不要关。

## 11. 手机访问 Atlas

手机也连接机器人热点：

```text
MYAP-XXXXXX
```

在 Atlas 上用 `ip -4 addr` 找到 Atlas 的地址，例如：

```text
192.168.4.2
```

手机浏览器打开：

```text
http://192.168.4.2:8000
```

如果能看到“智元素控制台”，就成功了。

## 12. 你现在最该做到哪一步

请先做到这一步：

```bash
uname -a
python3 --version
ip -4 addr
```

然后把输出发给我。

如果你连终端都还没打开，就拍一张 Atlas 接显示器后的屏幕照片，或者告诉我屏幕显示什么。
