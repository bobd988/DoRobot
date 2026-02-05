# VR 遥操机械臂系统 - 综合文档

> 最后更新: 2026-02-05

## 目录

- [项目概述](#项目概述)
- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [使用指南](#使用指南)
  - [VR 控制](#vr-控制)
  - [Leader-Follower 控制](#leader-follower-控制)
  - [数据录制](#数据录制)
- [技术文档](#技术文档)
  - [坐标系对应关系](#坐标系对应关系)
  - [旋转控制](#旋转控制)
  - [ARX X5 集成](#arx-x5-集成)
- [故障排查](#故障排查)
- [参考资料](#参考资料)

---

## 项目概述

本项目提供了基于 VR 头显和 Leader-Follower 模式的机械臂遥操控制系统，支持 ARX X5 和 SO101 机械臂。系统基于 Dora 框架构建，使用 WebSocket 进行 VR 数据传输，通过逆运动学(IK)将 VR 控制器位姿转换为机械臂关节角度。

### 主要功能

- VR 实时控制机械臂末端位姿
- 扳机键控制夹爪开合
- 握把键启用/禁用控制（离合器机制）
- 实时数据流监控
- 自动坐标系映射和校准
- 数据录制（DoRobot 格式）
- Leader-Follower 主从臂控制

### 支持的机械臂

- **ARX X5**: 6 DOF，CAN 总线通信
- **SO101**: USB 串口通信

### 支持的 VR 设备

- Meta Quest 2/3/Pro

---

## 快速开始

### 环境要求

#### 硬件要求

- ARX X5 机械臂（已连接并配置 CAN 接口）或 SO101 机械臂
- CAN 接口: `can0`（波特率 1Mbps，仅 ARX X5）
- Meta Quest VR 头显（Quest 2/3/Pro）
- 局域网连接（机器人主机和 VR 头显在同一网络）
- 奥比中光相机: Dabai DC1 (`/dev/video4`，数据录制时需要）

#### 软件环境

- **Conda 环境**: `dorobot`
- **Python 版本**: 3.11
- **关键依赖**:
  - dora-rs (Dora 框架)
  - pybullet (IK 求解)
  - pyarrow (数据传输)
  - X5 SDK (bimanual 库，仅 ARX X5)

### VR X5 快速启动

#### 1. 激活 Conda 环境

```bash
conda activate dorobot
```

#### 2. 进入工作目录

```bash
cd /home/dora/DoRobot/operating_platform/teleop_vr
```

#### 3. 启动系统

```bash
# 基本 VR 控制
./start_vr_x5.sh

# 带数据录制
bash run_vr_x5_record.sh

# 自定义数据集名称
REPO_ID="myuser/pick_apple" bash run_vr_x5_record.sh
```

#### 4. 连接 VR 头显

1. 在 Meta Quest 浏览器中访问: `https://<机器人主机IP>:8443`
   - 示例: `https://172.16.18.194:8443`

2. 接受自签名证书警告:
   - 点击"高级" → "继续访问"

3. 进入 VR 模式:
   - 点击页面右下角的 VR 图标
   - 允许浏览器访问 VR 设备

#### 5. 开始控制

**左手柄控制**:
- **握把键 (Grip)**: 按住启用控制，松开禁用
- **扳机键 (Trigger)**: 控制夹爪开合（0-1 映射到 0-2.0）
- **手柄位置**: 控制机械臂末端位置
- **手柄旋转**: 控制机械臂末端姿态（可配置）

---

## 系统架构

### VR-X5 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   VR-X5 数据采集系统                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │            DORA Dataflow (纯DORA架构)             │  │
│  │                                                   │  │
│  │  ┌──────────┐    ┌──────────┐   ┌────────────┐  │  │
│  │  │ camera_  │    │ vr_server│   │ arm_to_    │  │  │
│  │  │ orbbec   │───>│          │──>│ jointcmd_ik│  │  │
│  │  └──────────┘    └──────────┘   └────────────┘  │  │
│  │       │               │               │          │  │
│  │       │               │               │          │  │
│  │       └───────────────┴───────────────┘          │  │
│  │                       │                          │  │
│  │                       ▼                          │  │
│  │              ┌─────────────────┐                 │  │
│  │              │ data_recorder   │                 │  │
│  │              │ _v2.py          │                 │  │
│  │              │                 │                 │  │
│  │              │ - DoRobotDataset│                 │  │
│  │              │ - VR握把控制    │                 │  │
│  │              │ - 数据保存      │                 │  │
│  │              └─────────────────┘                 │  │
│  │                                                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  控制方式：VR手柄握把按钮（gripActive）                  │
│  数据流向：DORA节点 → data_recorder节点 → 数据保存      │
└─────────────────────────────────────────────────────────┘
```

### Dora 数据流节点

```
tick (50Hz)
  ↓
telegrip_https_ui (HTTPS UI服务器, 8443端口)

vr_ws_in (WebSocket服务器, 8442端口)
  ↓ vr_event
command_mux (命令复用器)
  ↓ arm_cmd
arm_to_jointcmd_ik (逆运动学求解器)
  ↓ action_joint
robot_driver_arx_x5 (X5机械臂驱动)
  ↓ joint (关节反馈)
  ↑ (反馈回IK节点)

vr_monitor (监控节点，监控所有数据流)
```

### 关键文件

| 文件 | 说明 |
|------|------|
| `dora_vr_x5.yml` | Dora 数据流配置文件（VR 控制） |
| `dora_vr_x5_record.yml` | Dora 数据流配置文件（带数据录制） |
| `robot_driver_arx_x5.py` | X5 机械臂驱动节点 |
| `arm_to_jointcmd_ik.py` | IK 求解节点 |
| `x5_kinematics_only.urdf` | X5 运动学 URDF 文件（简化版） |
| `vr_monitor.py` | 数据流监控脚本 |
| `data_recorder_v2.py` | 数据录制节点 |
| `start_vr_x5.sh` | 一键启动脚本（VR 控制） |
| `run_vr_x5_record.sh` | 一键启动脚本（带数据录制） |
| `cert.pem` / `key.pem` | SSL 证书（HTTPS/WSS 必需） |

---

## 使用指南

### VR 控制

#### 网络架构

```
┌─────────────────────┐
│   Meta Quest VR     │
│   (WiFi 连接)       │
└──────────┬──────────┘
           │ WiFi
           │
    ┌──────┴──────┐
    │   路由器     │
    └──────┬──────┘
           │ WiFi/以太网
           │
┌──────────┴──────────┐
│   控制电脑           │
│   (运行 VR 系统)     │
└──────────┬──────────┘
           │ CAN/USB
           │
┌──────────┴──────────┐
│   机械臂             │
│   (ARX X5/SO101)    │
└─────────────────────┘
```

#### VR 场景说明

进入 VR 场景后你会看到:

1. **深灰色背景** - 防止黑屏，提供基本的空间感
2. **左右手控制器**:
   - 每个控制器上有 **RGB 坐标轴**（红色=X轴，绿色=Y轴，蓝色=Z轴）
   - 控制器上方有**白色文本**显示:
     - `Pos: X Y Z` - 控制器的位置坐标（米）
     - `Rot: X Y Z` - 控制器的旋转角度（度）
     - `Z-Rot: XX.X°` - 当你按住握把时显示，表示绕 Z 轴的旋转

#### 操作流程

```
1. 戴上 Meta Quest 头显
   ↓
2. 访问 https://<电脑IP>:8443
   ↓
3. 接受 SSL 证书警告
   ↓
4. 点击页面上的 VR 图标进入 VR 模式
   ↓
5. 看到深灰色背景和两个控制器
   ↓
6. 移动手柄，确认文本信息实时更新
   ↓
7. 按住左手握把按钮（Grip）
   ↓
8. 移动左手柄，观察真实机械臂跟随
   ↓
9. 按下扳机键（Trigger），夹爪闭合
   ↓
10. 松开握把按钮，停止控制
   ↓
11. 重新调整手柄位置，继续操作
```

#### 离合器机制

系统使用**相对位移控制**而不是**绝对位置控制**:

```
初始状态:
  VR手柄在位置A
  机械臂在位置B

步骤1: 按下握把
  → 记录VR起点 = A
  → 记录机械臂起点 = B

步骤2: 移动手柄到C（相对A移动了Δ）
  → 机械臂移动到 B + Δ

步骤3: 松开握把
  → 机械臂停止在当前位置

步骤4: 移动手柄到D
  → 机械臂不动（因为握把未按下）

步骤5: 再次按下握把
  → 重新记录VR起点 = D
  → 记录机械臂起点 = 当前位置

步骤6: 移动手柄到E（相对D移动了Δ'）
  → 机械臂继续移动 Δ'
```

### Leader-Follower 控制

Leader-Follower 模式使用主臂（leader arm）控制从臂（follower arm），适合需要精确示教的场景。

详细配置请参考 `dora_leader_follower_x5.yml` 配置文件。

### 数据录制

#### 系统组成

- **VR手柄**: 主臂，控制机械臂运动
- **ARX-X5**: 从臂，执行VR命令
- **奥比中光相机**: Dabai DC1 (`/dev/video4`)
- **数据保存**: DoRobot格式（Parquet + MP4 + JSON）

#### 快速启动

```bash
cd /home/dora/DoRobot/operating_platform/teleop_vr

# 基本启动
bash run_vr_x5_record.sh

# 自定义数据集名称
REPO_ID="myuser/pick_apple" bash run_vr_x5_record.sh

# 自定义任务描述
SINGLE_TASK="抓取苹果放入篮子" bash run_vr_x5_record.sh
```

#### 操作流程

1. **启动系统**: 运行上述命令
2. **等待初始化**: 等待"All systems ready!"提示
3. **开始控制**:
   - 按下VR握把按钮
   - 移动手柄控制机械臂
   - 完成任务
4. **保存数据**:
   - 按 `n` 键: 保存当前episode，开始新episode
   - 按 `e` 键: 保存并退出
5. **查看数据**: 数据保存在 `./dataset/vr-x5-dataset/`

#### 控制说明

| 按键 | 功能 |
|------|------|
| VR握把 | 使能控制（按下=控制，松开=停止） |
| VR扳机 | 控制夹爪（0=张开，1=闭合） |
| `n` | 保存当前episode，开始新episode |
| `e` | 保存并退出 |
| `Ctrl+C` | 紧急停止 |

#### 数据格式

```
dataset/vr-x5-dataset/
├── data/chunk-000/
│   └── episode_000000.parquet    # 结构化数据
├── videos/chunk-000/camera_orbbec/
│   └── episode_000000.mp4        # 相机视频
└── meta/
    ├── info.json                 # 数据集信息
    └── episodes.jsonl            # episode元数据
```

**Parquet文件内容**:

```python
{
    'timestamp': float32,              # 时间戳
    'frame_index': int64,              # 帧索引
    'episode_index': int64,            # episode索引
    'observation.state': float32[6],   # ARX-X5关节角度
    'action': float32[7],              # IK命令（6关节+夹爪）
    'observation.images.camera_orbbec': str,  # 图像路径
}
```

#### 查看数据

**使用Python**:

```python
from operating_platform.dataset.dorobot_dataset import DoRobotDataset

# 加载数据集
dataset = DoRobotDataset("vr-x5-dataset", root="./dataset")

# 查看信息
print(f"Episodes: {dataset.num_episodes}")
print(f"Frames: {dataset.num_frames}")
print(f"Features: {dataset.features}")

# 读取第一个episode
episode = dataset[0]
print(f"State shape: {episode['observation.state'].shape}")
print(f"Action shape: {episode['action'].shape}")
```

**使用命令行**:

```bash
# 查看数据集信息
ls -lh ./dataset/vr-x5-dataset/

# 查看parquet文件
python -c "
import pandas as pd
df = pd.read_parquet('./dataset/vr-x5-dataset/data/chunk-000/episode_000000.parquet')
print(df.head())
print(df.columns)
"

# 播放视频
ffplay ./dataset/vr-x5-dataset/videos/chunk-000/camera_orbbec/episode_000000.mp4
```

---

## 技术文档

### 坐标系对应关系

#### VR手柄输入数据

| 数据类型 | 格式 | 说明 | 是否使用 |
|---------|------|------|---------|
| **位置 (pos)** | `[x, y, z]` | 手柄在3D空间的位置（米） | ✅ **使用** |
| **姿态 (quat)** | `[x, y, z, w]` | 手柄的旋转姿态（四元数） | ✅ **使用**（可配置） |
| **握把 (grip)** | `true/false` | 是否按下握把按钮 | ✅ **使用**（使能控制） |
| **扳机 (trigger)** | `0.0~1.0` | 扳机按下程度 | ✅ **使用**（控制夹爪） |

#### 位置映射（平移 → 平移）

**当前配置**（`dora_vr_x5.yml`）:

```yaml
IK_POS_MAP: "x,y,z"      # 坐标轴直接映射
IK_POS_SCALE: "1,1,1"    # 1:1缩放比例
IK_HOME_POS: "0.20,0.00,0.30"  # 初始位置（米）
```

**映射表**:

| VR手柄移动 | 机械臂末端移动 | 比例 | 说明 |
|-----------|--------------|------|------|
| 向右移动 (+X) | 向右移动 (+X) | 1:1 | 直接映射 |
| 向左移动 (-X) | 向左移动 (-X) | 1:1 | 直接映射 |
| 向上移动 (+Y) | 向上移动 (+Y) | 1:1 | 直接映射 |
| 向下移动 (-Y) | 向下移动 (-Y) | 1:1 | 直接映射 |
| 向前移动 (+Z) | 向前移动 (+Z) | 1:1 | 直接映射 |
| 向后移动 (-Z) | 向后移动 (-Z) | 1:1 | 直接映射 |

**注意**: 如果配置改为 `IK_POS_MAP: "-z,-x,y"`，则映射关系会变为:
- VR +X → 机械臂 -Z（向右移动→向后移动）
- VR +Y → 机械臂 -X（向上移动→向左移动）
- VR +Z → 机械臂 +Y（向前移动→向上移动）

#### 姿态映射（旋转 → 旋转）

| VR手柄旋转 | 机械臂末端旋转 | 状态 |
|-----------|--------------|------|
| Roll（翻滚） | ✅ **可控制** | 需启用 `IK_USE_ORIENTATION` |
| Pitch（俯仰） | ✅ **可控制** | 需启用 `IK_USE_ORIENTATION` |
| Yaw（偏航） | ✅ **可控制** | 需启用 `IK_USE_ORIENTATION` |

#### 按钮映射

| VR手柄输入 | 机械臂输出 | 映射关系 |
|-----------|-----------|---------|
| 握把按钮 | 使能/失能控制 | 按下=控制机械臂，松开=停止 |
| 扳机按钮 | 夹爪开合 | 0.0=完全张开，1.0=完全闭合 |

#### 配置参数说明

```yaml
arm_to_jointcmd_ik:
  env:
    # URDF配置
    URDF_PATH: "/path/to/x5_kinematics_only.urdf"
    EE_LINK: "link6"  # 末端执行器链接名称

    # 初始位置（米）
    IK_HOME_POS: "0.20,0.00,0.30"
    # 说明：机械臂的初始位置，格式为 "X,Y,Z"

    # 坐标系映射
    IK_POS_MAP: "x,y,z"
    # 说明：VR坐标系到机械臂坐标系的映射
    # 格式：每个位置对应VR的哪个轴（可加负号表示反向）
    # 示例：
    #   "x,y,z"    - 直接映射
    #   "-x,-y,-z" - 全部反向
    #   "-z,-x,y"  - X→-Z, Y→-X, Z→Y

    # 位置缩放
    IK_POS_SCALE: "1,1,1"
    # 说明：每个轴的缩放因子
    # 示例：
    #   "1,1,1"     - 1:1映射（手柄移动10cm，机械臂移动10cm）
    #   "0.5,0.5,0.5" - 减小灵敏度（手柄移动10cm，机械臂移动5cm）
    #   "2,2,2"     - 增加灵敏度（手柄移动10cm，机械臂移动20cm）

    # 姿态控制
    IK_USE_ORIENTATION: "1"
    # 说明：是否使用VR手柄姿态控制机械臂末端姿态
    # "0" = 禁用（只控制位置）
    # "1" = 启用（控制位置+姿态）

    # 关节微调（度）
    JOINT_OFFSET_DEG: "0,0,0,0,20,0"
    # 说明：6个关节的角度偏置，用于微调零位

    JOINT_SIGN: "1,1,1,1,1,1"
    # 说明：6个关节的方向（1或-1），一般不需要修改

    # IK参数
    IK_ITERS: "80"              # IK迭代次数
    IK_THRESH: "1e-4"           # IK收敛阈值
    IK_SEND_DT: "0.02"          # 发送间隔（秒），建议50Hz
    IK_REQUIRE_JOINT_ON_ENABLE: "1"  # 需要关节反馈才能启用
```

### 旋转控制

#### 功能状态

✅ **已启用** - VR手柄旋转控制机械臂末端姿态

#### 快速开关

**禁用旋转控制**（如果效果不好）:

编辑 `dora_vr_x5_record.yml` 第82行:

```yaml
# 改为 "0" 禁用
IK_USE_ORIENTATION: "0"
```

**启用旋转控制**:

```yaml
# 改为 "1" 启用（默认）
IK_USE_ORIENTATION: "1"
```

### ARX X5 集成

#### 硬件接口

- **接口类型**: CAN 总线
- **CAN 端口**: can0（默认）
- **波特率**: 由 X5 SDK 自动配置
- **控制方式**: 位置控制 + 夹爪控制

#### 机械臂规格

- **自由度**: 6 DOF（6个旋转关节）
- **末端执行器**: 1个夹爪
- **关节编号**: Joint1-Joint6（从基座到末端）
- **夹爪范围**: 0.0 - 2.0（X5 SDK单位）

#### X5 SDK 集成

**SDK 路径配置**:

```bash
# X5 SDK 安装路径
X5_SDK_PATH="/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"

# 库文件路径
LD_LIBRARY_PATH="${X5_SDK_PATH}/bimanual/api/arx_x5_src:${X5_SDK_PATH}/bimanual/api:/usr/local/lib"

# Python 路径
PYTHONPATH="${X5_SDK_PATH}/bimanual/api:${X5_SDK_PATH}/bimanual/api/arx_x5_python"
```

#### 单位转换

**问题**: IK 求解器输出度数（degrees），X5 SDK 期望弧度（radians）

**解决方案**:

```python
# 在发送到 X5 前转换单位
joint_array_rad = np.array([np.deg2rad(x) for x in joint_positions[:6]])
arm.set_joint_positions(joint_array_rad)
```

#### 夹爪映射

- **VR 扳机值**: 0.0 - 1.0
- **X5 夹爪值**: 0.0 - 2.0

```python
gripper_x5 = float(gripper) * 2.0
arm.set_catch_pos(pos=gripper_x5)
```

#### 完整数据流

```
IK 求解器
    ↓ action_joint (PyArrow Array)
    ↓ [j1_deg, j2_deg, j3_deg, j4_deg, j5_deg, j6_deg, gripper_0_100]
    ↓
robot_driver_arx_x5
    ↓ 单位转换（度 → 弧度）
    ↓ [j1_rad, j2_rad, j3_rad, j4_rad, j5_rad, j6_rad]
    ↓
X5 SDK
    ↓ arm.set_joint_positions(joints_rad)
    ↓ arm.set_catch_pos(gripper_x5)
    ↓
CAN 总线
    ↓
ARX X5 机械臂
```

---

## 故障排查

### 系统监控

系统启动后，`vr_monitor`节点会自动监控所有数据流，每5秒打印一次统计信息:

```
========================================
VR X5 系统状态摘要 (运行时间: 30.2秒)
========================================

VR连接状态:
  设备IP: 172.16.18.186
  连接状态: 已连接
  最后更新: 0.1秒前

控制状态:
  使能状态: 已启用 ✓
  夹爪值: 0.45
  末端位置: (0.123, -0.045, 0.678)

数据流统计:
  VR事件:       1537 条
  机械臂命令:   1540 条
  关节命令:     1520 条
  关节反馈:     1518 条

性能指标:
  VR频率:   8.8 Hz
  命令频率: 50.2 Hz
```

### 查看详细日志

```bash
# 查看所有运行中的数据流
dora list

# 查看特定节点的日志
dora logs <dataflow-uuid>

# 实时跟踪监控节点日志
dora logs vr_monitor --follow

# 实时跟踪X5驱动节点日志
dora logs arm_arx_x5 --follow
```

### 常见问题

#### Q1: VR设备无法连接

**症状**: VR头显无法访问HTTPS页面

**排查步骤**:
1. 确认机器人主机和VR头显在同一局域网
2. 检查防火墙是否开放8443和8442端口
3. 确认SSL证书存在: `ls cert.pem key.pem`
4. 查看UI服务器日志: `dora logs telegrip_https_ui --follow`

#### Q2: 机械臂不响应VR控制

**症状**: VR连接正常，但机械臂不动

**排查步骤**:

1. **检查关节命令是否生成**:
   ```bash
   dora logs vr_monitor --follow
   ```
   查看"关节命令"是否大于0

2. **检查CAN接口**:
   ```bash
   ip link show can0
   ```
   应显示`UP`状态

3. **检查X5驱动日志**:
   ```bash
   dora logs arm_arx_x5 --follow
   ```
   查看是否有错误信息

4. **检查IK求解**:
   ```bash
   dora logs arm_to_jointcmd_ik --follow
   ```
   查看是否有"SENT action_joint"消息

#### Q3: 启动失败，提示"Camera not found"

**排查步骤**:
```bash
ls -l /dev/video4
v4l2-ctl --list-devices
```

#### Q4: 启动失败，提示"CAN interface not found"

**解决方案**:
```bash
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ip link show can0
```

#### Q5: 手柄移动方向和机械臂移动方向不一致

**解决方案**: 修改 `IK_POS_MAP` 参数。常用配置:
- `"x,y,z"` - 直接映射
- `"-x,y,z"` - X轴反向
- `"-z,-x,y"` - 旋转坐标系

#### Q6: 机械臂移动太快或太慢

**解决方案**: 修改 `IK_POS_SCALE` 参数:
- 太快: 改为 `"0.5,0.5,0.5"`
- 太慢: 改为 `"2,2,2"`

#### Q7: 按住握把后机械臂突然跳动

**原因**: VR起点和机械臂当前位置不匹配

**解决方法**:
1. 确保 `IK_REQUIRE_JOINT_ON_ENABLE: "1"`
2. 在按握把前，将手柄移动到合适的位置

#### Q8: 数据没有保存

**排查步骤**:
1. 是否按下了VR握把？（必须按下才开始录制）
2. 是否按了Ctrl+C保存？
3. 查看日志: `dora logs data_recorder --follow`

#### Q9: 视频是黑屏

**测试相机**:
```bash
ffplay /dev/video4
```

#### Q10: 关节命令为0（死锁问题）

**症状**: 监控显示"关节命令: 0 条"

**原因**: IK节点等待关节反馈，但驱动未发送初始反馈

**解决方案**:
- 已在 `robot_driver_arx_x5.py` 中修复
- 驱动启动时会自动发送初始关节反馈
- 查看日志确认: `✓ Sent initial joint feedback to IK node`

### 停止系统

```bash
# 停止所有数据流
dora destroy

# 或停止特定数据流
dora stop <dataflow-uuid>
```

### 重启系统

```bash
# 停止现有数据流
dora destroy

# 重新启动
./start_vr_x5.sh
```

---

## 参考资料

### 相关文档

- [ARX_X5_VR控制技术文档.md](./ARX_X5_VR控制技术文档.md) - ARX X5 集成详细说明
- [VR_X5_坐标系对应关系.md](./VR_X5_坐标系对应关系.md) - 坐标系映射详细说明
- [VR_X5_与SO101架构对比.md](./VR_X5_与SO101架构对比.md) - 架构差异分析
- [VR_X5_使用文档.md](./VR_X5_使用文档.md) - 详细使用说明
- [VR旋转控制-快速参考.md](./VR旋转控制-快速参考.md) - 旋转控制快速参考
- [README-VR.md](./README-VR.md) - VR 系统基础指南
- [README-数据录制.md](./README-数据录制.md) - 数据录制快速指南
- [README-最终使用指南.md](./README-最终使用指南.md) - 最终使用指南

### 外部资源

- Dora框架: https://github.com/dora-rs/dora
- ARX X5 SDK: `/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python`
- PyBullet文档: https://pybullet.org/

### 快速命令参考

```bash
# 启动系统
conda activate dorobot
cd /home/dora/DoRobot/operating_platform/teleop_vr
./start_vr_x5.sh

# 监控系统
dora list
dora logs vr_monitor --follow

# 停止系统
dora destroy

# 检查CAN接口
ip link show can0
candump can0

# 查看进程
ps aux | grep dora
```

### 性能指标

- **VR采样率**: 通常5-10Hz（受VR设备和网络限制）
- **命令发送率**: 最高50Hz（受 `DT` 参数限制）
- **IK求解时间**: <5ms（PyBullet DIRECT模式）
- **端到端延迟**: 通常100-200ms

### 适配其他机械臂的关键点

#### 1. 机械臂驱动节点 (`robot_driver_xxx.py`)
- 替换机械臂 SDK 导入和初始化代码
- 确认并转换单位系统（度/弧度）
- 适配夹爪控制接口和数值范围
- 实现关节位置读取和反馈机制

#### 2. URDF 运动学模型 (`xxx_kinematics.urdf`)
- 创建目标机械臂的 URDF 文件
- 定义正确的关节数量和类型
- 设置关节限位和 DH 参数
- 指定末端执行器链接名称

#### 3. IK 求解器配置 (`arm_to_jointcmd_ik.py`)
- 设置关节数量 `NUM_JOINTS`
- 配置初始位置 `IK_HOME_POS`
- 调整关节符号 `JOINT_SIGN` 和偏置 `JOINT_OFFSET_DEG`
- 修改数据数组长度（关节数 + 1）

#### 4. Dora 数据流配置 (`dora_vr_xxx.yml`)
- 更新驱动节点的 ID 和脚本路径
- 配置机械臂特定的环境变量
- 调整节点间的输入输出连接
- 设置通信接口参数（CAN/串口/以太网）

#### 5. 数据格式一致性检查
- 确保 IK 输出数组长度 = 关节数 + 1
- 验证驱动节点期望的输入格式
- 检查监控节点的数据解析逻辑
- 统一所有节点的 `NUM_JOINTS` 配置

---

## 维护记录

| 日期 | 修改内容 | 修改人 |
|------|----------|--------|
| 2026-02-05 | 创建综合文档 | Claude Code |
| 2026-01-30 | 修复关节反馈死锁问题 | Claude |
| 2026-02-02 | 添加数据录制功能 | Claude Code |
| 2026-02-02 | 添加旋转控制功能 | Claude Code |

---

**文档版本**: v1.0
**最后更新**: 2026-02-05
**维护者**: Claude Code
**状态**: ✅ 已完成并测试

---

## 联系支持

如遇到问题，请检查:
1. 本文档的"故障排查"章节
2. Dora日志输出
3. 机械臂驱动日志
4. 相关技术文档

**工作目录**: `/home/dora/DoRobot-vr/operating_platform/teleop_vr`

