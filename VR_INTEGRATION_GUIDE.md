# VR 模块集成指南

## 集成完成状态

✅ VR 功能模块已成功集成到 `/home/demo/Public/DoRobot`

### 集成内容

1. **VR 操控模块**: `operating_platform/teleop_vr/`
2. **用户文档**: `README-VR.md`
3. **配置文件**: 已更新所有路径指向新位置

---

## 目录结构

```
/home/demo/Public/DoRobot/
├── README-VR.md                          # VR 模块使用文档
├── VR_INTEGRATION_GUIDE.md               # 本文件（集成指南）
└── operating_platform/
    └── teleop_vr/                        # VR 操控模块
        ├── dora_vr_teleoperate.yml       # Dora 数据流配置（已更新路径）
        ├── tick.py                       # 时钟节点
        ├── telegrip_https_ui.py         # HTTPS 服务器
        ├── vr_ws_in.py                  # WebSocket 输入
        ├── command_mux.py               # 命令解析器
        ├── arm_to_jointcmd_ik.py        # IK 求解器
        ├── sim_viz.py                   # 仿真可视化
        ├── robot_driver_so100_follower.py  # 硬件驱动
        ├── robot_driver_stub.py         # 调试驱动
        ├── arm_to_jointcmd_stub.py      # 调试 IK
        ├── VR_SYSTEM_DOCUMENTATION.md   # 详细技术文档
        ├── web-ui/                      # VR 网页界面
        ├── urdf/                        # 机器人模型
        └── .calibration/                # 校准数据
```

---

## 快速启动

### 1. 生成 SSL 证书（首次使用）

```bash
cd /home/demo/Public/DoRobot/operating_platform/teleop_vr
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### 2. 启动 VR 系统

```bash
# 进入 VR 操控目录
cd /home/demo/Public/DoRobot/operating_platform/teleop_vr

# 启动 Dora 守护进程
dora up

# 启动 VR 操控数据流
dora start dora_vr_teleoperate.yml
```

### 3. 连接 VR 头显

1. 在 Meta Quest 上打开浏览器
2. 访问 `https://<机器人IP>:8443`
3. 接受自签名证书警告
4. 进入 VR 模式
5. 使用左手柄控制机械臂

### 4. 停止系统

```bash
dora stop <dataflow-uuid>
# 或
dora destroy
```

---

## 配置说明

### 已更新的路径

配置文件 `dora_vr_teleoperate.yml` 中的以下路径已更新：

| 配置项 | 旧路径 | 新路径 |
|--------|--------|--------|
| URDF_PATH | `/home/demo/synk/dora-dorobot/...` | `/home/demo/Public/DoRobot/...` |
| CALIB_PATH | `/home/demo/synk/dora-dorobot/...` | `/home/demo/Public/DoRobot/...` |
| arm_so101_follower | `/home/demo/synk/dora-dorobot/...` | `/home/demo/Public/DoRobot/...` |

所有路径现在都指向 `/home/demo/Public/DoRobot/operating_platform/`。

---

## 与原有系统的集成

### 共享组件

VR 模块使用以下共享组件：

1. **机械臂驱动**: `operating_platform/robot/components/arm_normal_so101_v1/main.py`
   - VR 模块通过 Dora 数据流调用此驱动
   - 与其他操控方式（如键盘、示教等）共享同一驱动

2. **校准数据**: `operating_platform/teleop_vr/.calibration/SO101-follower.json`
   - 机械臂关节校准参数
   - 确保 VR 控制的精度

3. **URDF 模型**: `operating_platform/teleop_vr/urdf/SO100/so100.urdf`
   - 机器人运动学模型
   - 用于 IK 求解和仿真

### 独立组件

VR 模块的以下组件是独立的：

1. **Web 界面**: `teleop_vr/web-ui/`
2. **VR 数据处理**: `vr_ws_in.py`, `command_mux.py`
3. **IK 求解器**: `arm_to_jointcmd_ik.py`
4. **仿真可视化**: `sim_viz.py`

---

## 使用场景

### 场景 1: VR 远程操控

```bash
cd /home/demo/Public/DoRobot/operating_platform/teleop_vr
dora up
dora start dora_vr_teleoperate.yml
```

在 Meta Quest 上访问 `https://<机器人IP>:8443`

### 场景 2: 仅仿真模式（无硬件）

如果需要在没有真实硬件的情况下测试：

1. 编辑 `dora_vr_teleoperate.yml`
2. 将 `arm_so101_follower` 节点替换为 `robot_driver_stub.py`
3. 将 `arm_to_jointcmd_ik.py` 替换为 `arm_to_jointcmd_stub.py`

### 场景 3: 与其他操控方式结合

VR 模块可以与其他操控方式（如键盘、示教器）配合使用：

- 不同操控方式可以通过不同的 Dora 数据流启动
- 共享同一个机械臂驱动
- 注意避免同时启动多个控制数据流

---

## 网络配置

### 端口使用

| 端口 | 协议 | 用途 |
|------|------|------|
| 8443 | HTTPS | VR 网页界面 |
| 8442 | WSS | WebSocket 数据传输 |

### 防火墙设置

如果无法访问，请确保防火墙允许这些端口：

```bash
# 检查防火墙状态
sudo ufw status

# 允许端口（如果需要）
sudo ufw allow 8443/tcp
sudo ufw allow 8442/tcp
```

---

## 故障排除

### 问题 1: 找不到机械臂设备

**错误**: `Cannot find device at /dev/ttyACM0`

**解决方案**:
```bash
# 检查设备连接
ls -l /dev/ttyACM*

# 检查设备权限
sudo chmod 666 /dev/ttyACM0
```

### 问题 2: 路径错误

**错误**: `FileNotFoundError: [Errno 2] No such file or directory`

**解决方案**:
- 确认所有路径都已更新为 `/home/demo/Public/DoRobot/...`
- 检查 `dora_vr_teleoperate.yml` 中的路径配置

### 问题 3: SSL 证书问题

**错误**: `SSL certificate verify failed`

**解决方案**:
```bash
cd /home/demo/Public/DoRobot/operating_platform/teleop_vr
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

---

## 开发与调试

### 查看日志

```bash
# 查看所有节点日志
dora logs <dataflow-uuid>

# 查看特定节点日志
dora logs <dataflow-uuid> --node vr_ws_in
dora logs <dataflow-uuid> --node arm_to_jointcmd_ik
dora logs <dataflow-uuid> --node arm_so101_follower
```

### 调试模式

在 `dora_vr_teleoperate.yml` 中调整以下参数：

```yaml
# 增加调试输出
VR_PRINT_FIRST_N: "10"        # 打印前 10 条 VR 消息
MUX_HEARTBEAT_SEC: "1.0"      # 每秒打印心跳日志
```

### 测试 WebSocket 连接

```bash
# 使用 wscat 测试 WebSocket
npm install -g wscat
wscat -c wss://localhost:8442 --no-check
```

---

## 下一步

1. **阅读详细文档**: 查看 `README-VR.md` 了解完整功能
2. **技术细节**: 查看 `operating_platform/teleop_vr/VR_SYSTEM_DOCUMENTATION.md`
3. **调整参数**: 根据实际情况调整 `dora_vr_teleoperate.yml` 中的配置
4. **测试系统**: 先使用仿真模式测试，再连接真实硬件

---

## 维护建议

### 定期检查

- SSL 证书有效期（默认 365 天）
- 机械臂校准数据是否需要更新
- Dora 框架版本更新

### 备份重要文件

```bash
# 备份配置文件
cp dora_vr_teleoperate.yml dora_vr_teleoperate.yml.backup

# 备份校准数据
cp -r .calibration .calibration.backup
```

### 更新路径

如果移动 DoRobot 目录，需要更新 `dora_vr_teleoperate.yml` 中的以下路径：
- URDF_PATH
- CALIB_PATH
- arm_so101_follower 的 main.py 路径

---

## 联系与支持

- **用户文档**: `README-VR.md`
- **技术文档**: `operating_platform/teleop_vr/VR_SYSTEM_DOCUMENTATION.md`
- **配置文件**: `operating_platform/teleop_vr/dora_vr_teleoperate.yml`

集成完成时间: 2026-01-27
