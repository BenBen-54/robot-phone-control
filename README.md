# Robot Phone Control Starter

手机端控制智元素机器人的最小 starter。

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

