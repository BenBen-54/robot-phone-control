# Atlas DK A2 部署手机控制服务

这份文档从“已经会打开 Atlas 终端”开始。若你还不知道怎么开机、登录和打开命令行，先看：

```text
docs/atlas_beginner_start.md
```

目标是让 Atlas DK A2 代替电脑：

```text
手机浏览器
  -> Atlas DK A2 上的 FastAPI 服务
  -> UDP 9999
  -> 智元素机器人
```

## 0. 推荐网络结构

先使用最简单的网络结构：

```text
机器人开启 MYAP-XXXXXX 热点
Atlas 连接 MYAP-XXXXXX
手机连接 MYAP-XXXXXX
```

机器人热点密码通常是：

```text
88888888
```

机器人 IP 通常是：

```text
192.168.4.1
```

注意：机器人热点可能只允许少量设备同时连接。部署和测试时，最终只保留 Atlas 和手机连接机器人热点，电脑可以先断开。

## 1. 先确认 Atlas 能打开终端

你可以用任意一种方式进入 Atlas：

- 显示器 + 键盘 + 鼠标直接操作。
- 通过 SSH 远程登录。
- 通过你已有的 Atlas 开发环境终端。

在 Atlas 终端执行：

```bash
uname -a
python3 --version
ip -4 addr
```

如果 `python3 --version` 能显示 Python 版本，就可以继续。

## 2. 先让 Atlas 连接互联网安装依赖

安装依赖时，Atlas 需要能访问 Python 包源。你可以先让 Atlas 连接家里/实验室 WiFi 或网线。

在 Atlas 上确认能联网：

```bash
ping -c 2 pypi.org
```

如果不能联网，先不要接机器人热点，先解决 Atlas 上网问题。

## 3. 把项目复制到 Atlas

### 方案 A：用 U 盘复制

在 Windows 上把项目文件夹复制到 U 盘。不要复制 `.venv` 目录。

需要复制这些内容：

```text
server/
tools/
docs/
scripts/
requirements.txt
README.md
PROJECT_NOTES.md
```

在 Atlas 上建议放到：

```bash
~/robot-phone-control
```

### 方案 B：用 scp 复制

如果电脑和 Atlas 在同一个网络，可以在 Windows PowerShell 执行：

```powershell
scp -r C:\Users\20914\Documents\robot-phone-control 用户名@Atlas_IP:~/robot-phone-control
```

把 `用户名` 和 `Atlas_IP` 换成你的 Atlas 登录用户名和 IP。

如果复制了 `.venv`，问题也不大，但 Atlas 上不能直接用 Windows 的 `.venv`，后面仍然要重新创建 Linux 虚拟环境。

## 4. 在 Atlas 上安装项目依赖

进入项目目录：

```bash
cd ~/robot-phone-control
```

给脚本执行权限：

```bash
chmod +x scripts/*.sh
```

安装依赖：

```bash
./scripts/install_atlas.sh
```

如果提示缺少 `venv`：

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
./scripts/install_atlas.sh
```

## 5. 让 Atlas 连接机器人热点

安装依赖完成后，把 Atlas 网络切到机器人热点：

```text
MYAP-XXXXXX
密码 88888888
```

如果 Atlas 有桌面界面，可以直接在 WiFi 图标里连接。

如果只能用命令行，并且系统使用 NetworkManager，可以先查看 WiFi：

```bash
nmcli dev wifi list
```

连接机器人热点：

```bash
nmcli dev wifi connect "MYAP-XXXXXX" password "88888888"
```

确认 Atlas 拿到 `192.168.4.x` 地址：

```bash
ip -4 addr
```

确认能连到机器人：

```bash
ping -c 2 192.168.4.1
```

## 6. 在 Atlas 上测试 UDP 控制

先不要启动网页服务，先跑命令行测试：

```bash
cd ~/robot-phone-control
.venv/bin/python tools/zys_udp_test.py --robot-ip 192.168.4.1 demo
```

架空轮子后，测试低速移动：

```bash
.venv/bin/python tools/zys_udp_test.py --robot-ip 192.168.4.1 move --angle 0 --speed 10 --turn 0 --duration 0.25
```

如果这里能动，说明 Atlas 已经可以控制机器人。

## 7. 在 Atlas 上启动网页控制服务

```bash
cd ~/robot-phone-control
./scripts/run_atlas.sh
```

看到类似下面的输出就表示服务启动了：

```text
Uvicorn running on http://0.0.0.0:8000
```

这个终端窗口不要关。

## 8. 手机访问 Atlas

手机也连接同一个机器人热点 `MYAP-XXXXXX`。

在 Atlas 上查 IP：

```bash
ip -4 addr
```

找到 Atlas 的 `192.168.4.x` 地址。假设是：

```text
192.168.4.2
```

手机浏览器打开：

```text
http://192.168.4.2:8000
```

然后按之前的顺序测试：

1. 电池
2. 模式0
3. 速度 10
4. 前进，松手停止
5. 后退、左移、右移、左转、右转

## 9. 常见问题

如果手机打不开网页：

- 确认手机和 Atlas 都在 `MYAP-XXXXXX`。
- 确认访问的是 Atlas 的 `192.168.4.x`，不是机器人 `192.168.4.1`。
- 确认服务启动命令里有 `--host 0.0.0.0`。
- 如果系统有防火墙，临时允许 8000 端口。

如果 Atlas 能打开网页但机器人不动：

- 关闭官方 APP、电脑端服务、动作编辑器。
- 运行：

```bash
.venv/bin/python tools/zys_udp_test.py --robot-ip 192.168.4.1 demo
```

- 如果命令行也不能动，优先检查 Atlas 是否还连在机器人热点上。

如果 pip 安装失败：

- 先切回可上网网络。
- 再执行：

```bash
./scripts/install_atlas.sh
```

依赖安装完成后，再切回机器人热点。

## 10. 下一步

网页控制服务在 Atlas 上稳定后，再接摄像头和 OCR：

```text
Atlas 摄像头拍照
OCR 识别“位置一 劈砍”
解析识别文本
调用现有 UDP 动作控制
```
