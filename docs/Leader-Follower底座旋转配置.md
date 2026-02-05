# Leader-Follower X5 底座旋转配置说明

> 文档创建时间：2026-02-04
> 适用系统：Leader-Follower X5 (Feetech → ARX-X5)

---

## 📋 目录

1. [系统架构](#系统架构)
2. [初始位置定义](#初始位置定义)
3. [底座旋转配置](#底座旋转配置)
4. [配置方法](#配置方法)
5. [测试验证](#测试验证)

---

## 系统架构

### 数据流程

```
Leader Arm (Feetech STS3215)
    ↓ (弧度值)
Adapter (leader_follower_adapter.py)
    ↓ (度数值 + 坐标转换)
ARX X5 Follower
    ↓ (机械臂运动)
```

### 节点说明

| 节点 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `arm_leader` | 读取主臂位置 | 定时器 | joint (弧度) |
| `adapter` | 坐标转换和映射 | leader_joint | action_joint (度数) |
| `arm_follower_x5` | 控制从臂 | action_joint | joint (反馈) |

---

## 初始位置定义

### Leader Arm 初始位置

**零位对齐机制**：
- 启动后等待 **10 帧**（约 0.5 秒）
- 记录主臂的当前物理位置作为 **零点**
- 后续所有运动都相对于这个零点

**代码位置**：`leader_follower_adapter.py:84-92`

```python
# 零位对齐：记录初始位置
if cmd_count >= zero_align_delay:
    initial_position = joint_radians[:6]  # 记录前6个关节
    zero_aligned = True
    print(f"Zero position recorded: {initial_position}")
```

**重要提示**：
- 启动系统前，将主臂摆放到你希望的 **零位姿态**
- 这个姿态将成为后续所有运动的参考点
- 从臂会跟随主臂相对于零位的运动

### ARX X5 初始位置

**物理位置决定**：
- 由 `SingleArm` 初始化时的实际物理位置决定
- 没有预定义的 home 位置
- 使用 `arm.get_joint_positions()` 获取当前位置

**建议**：
- 启动前将从臂摆放到安全的初始姿态
- 确保从臂有足够的运动空间

---

## 底座旋转配置

### 为什么需要旋转底座？

**常见场景**：
1. 机械臂安装方向与主臂不一致
2. 工作空间布局需要调整
3. 避免机械臂与环境碰撞

### 旋转方向说明

```
从上往下看机械臂底座：

        前 (0°)
         ↑
         |
左 ←-----+----→ 右
         |
         ↓
        后

顺时针旋转 90°：前 → 右
逆时针旋转 90°：前 → 左
旋转 180°：前 → 后
```

### 配置参数

**环境变量**：`BASE_ROTATION_OFFSET`

| 值 | 效果 | 说明 |
|----|------|------|
| `0` | 不旋转 | 默认方向 |
| `90` | 顺时针 90° | 前方变为右方 |
| `-90` | 逆时针 90° | 前方变为左方 |
| `180` | 旋转 180° | 前方变为后方 |
| 任意角度 | 自定义旋转 | 例如 `45`, `-135` |

---

## 配置方法

### 方法 1：修改 DORA 配置文件（推荐）

**文件**：`operating_platform/teleop_vr/dora_leader_follower_x5.yml`

**位置**：adapter 节点的 env 部分

```yaml
# 适配器节点 - 将主臂弧度值转换为从臂度数值
- id: adapter
  path: /home/dora/miniconda3/envs/dorobot/bin/python3
  args: -u /home/dora/DoRobot-vr/operating_platform/teleop_vr/leader_follower_adapter.py
  inputs:
    leader_joint: arm_leader/joint
  outputs:
    - action_joint
  env:
    # 底座旋转偏移（度数）
    # 90 = 顺时针旋转90度
    # -90 = 逆时针旋转90度
    # 0 = 不旋转
    BASE_ROTATION_OFFSET: "90"  # ← 修改这里

    # 零位对齐配置
    ENABLE_ZERO_ALIGN: "true"
    ZERO_ALIGN_DELAY: "10"

    # EMA平滑系数（0.0-1.0，越小越平滑但响应越慢）
    EMA_ALPHA: "0.2"
```

**修改步骤**：
1. 打开配置文件
2. 找到 `adapter` 节点
3. 修改 `BASE_ROTATION_OFFSET` 的值
4. 保存文件
5. 重新启动系统

### 方法 2：直接修改代码

**文件**：`operating_platform/teleop_vr/leader_follower_adapter.py`

**位置**：Line 42-44（环境变量读取）

```python
# 底座旋转偏移（度数）
# 设置为 90 表示顺时针旋转90度，-90 表示逆时针旋转90度
base_rotation_offset = float(os.getenv("BASE_ROTATION_OFFSET", "90"))
print(f"[adapter] Base rotation offset: {base_rotation_offset}°", flush=True)
```

**位置**：Line 110-116（应用旋转）

```python
# 关节特殊处理
if i == 0:
    # 底座旋转偏移（从环境变量读取）
    deg = deg + base_rotation_offset
elif i == 1:
    # 第二个关节反向
    deg = -deg
```

---

## 测试验证

### 启动系统

```bash
# 启动 Leader-Follower 遥操作
bash scripts/run_so101.sh
```

### 验证步骤

**1. 检查日志输出**

启动后应该看到：
```
[adapter] Leader-Follower Adapter started
[adapter] Base rotation offset: 90.0°  # ← 确认旋转角度
[adapter] Zero position recorded: [...]
```

**2. 测试运动方向**

| 主臂动作 | 预期从臂动作（90°旋转） |
|---------|----------------------|
| 向前移动 | 向右移动 |
| 向右移动 | 向后移动 |
| 向后移动 | 向左移动 |
| 向左移动 | 向前移动 |

**3. 微调旋转角度**

如果方向不完全对齐：
- 增加角度：`BASE_ROTATION_OFFSET: "95"`
- 减少角度：`BASE_ROTATION_OFFSET: "85"`
- 反向旋转：`BASE_ROTATION_OFFSET: "-90"`

### 常见问题

**问题 1：从臂运动方向完全相反**

**解决方法**：
```yaml
# 将旋转角度加/减 180 度
BASE_ROTATION_OFFSET: "270"  # 原来是 90
# 或
BASE_ROTATION_OFFSET: "-90"  # 原来是 90
```

**问题 2：从臂运��方向偏移**

**解决方法**：
```yaml
# 微调角度，每次调整 5-10 度
BASE_ROTATION_OFFSET: "95"   # 原来是 90
BASE_ROTATION_OFFSET: "85"   # 原来是 90
```

**问题 3：从臂不跟随主臂运动**

**检查项**：
1. 确认零位对齐成功（查看日志）
2. 检查从臂是否正常初始化
3. 检查 CAN 总线连接

---

## 高级配置

### 多关节旋转映射

如果需要更复杂的坐标转换，可以修改 `leader_follower_adapter.py`：

```python
# 关节特殊处理
if i == 0:
    # 底座旋转偏移
    deg = deg + base_rotation_offset
elif i == 1:
    # 第二个关节反向
    deg = -deg
elif i == 2:
    # 第三个关节添加偏移
    deg = deg + 10  # 例如：添加10度偏移
```

### 禁用零位对齐

如果不需要零位对齐（使用绝对位置）：

```yaml
env:
  ENABLE_ZERO_ALIGN: "false"  # 禁用零位对齐
  BASE_ROTATION_OFFSET: "90"
```

### 调整平滑系数

如果从臂响应太慢或太抖动：

```yaml
env:
  EMA_ALPHA: "0.3"  # 增加响应速度（0.0-1.0）
  # 0.1 = 非常平滑，响应慢
  # 0.5 = 平衡
  # 0.9 = 响应快，可能抖动
```

---

## 参考资料

### 相关文件

**配置文件**：
- `operating_platform/teleop_vr/dora_leader_follower_x5.yml` - DORA 配置
- `operating_platform/teleop_vr/leader_follower_adapter.py` - 适配器代码
- `operating_platform/teleop_vr/robot_driver_arx_x5.py` - X5 驱动

**文档**：
- `docs/数据保存问题修复总结.md` - 数据保存问题
- `operating_platform/teleop_vr/README-最终使用指南.md` - 使用指南

### 坐标系说明

**Leader Arm (Feetech)**：
- 关节 0：底座旋转（水平）
- 关节 1：肩部俯仰
- 关节 2：肘部俯仰
- 关节 3：腕部俯仰
- 关节 4：腕部旋转
- 关节 5：腕部翻转
- 关节 6：夹爪

**ARX X5 Follower**：
- 关节 0：底座旋转（水平）
- 关节 1：肩部俯仰
- 关节 2：肘部俯仰
- 关节 3：腕部俯仰
- 关节 4：腕部旋转
- 关节 5：腕部翻转
- 夹爪：独立控制

---

## 总结

✅ **已实现功能**：
- 底座旋转偏移配置
- 环境变量灵活配置
- 零位对齐机制
- 平滑滤波和死区过滤

🎯 **配置要点**：
- 修改 `BASE_ROTATION_OFFSET` 环境变量
- 顺时针旋转使用正值（如 `90`）
- 逆时针旋转使用负值（如 `-90`）
- 可以使用任意角度（如 `45`, `135`）

📊 **测试建议**：
- 先使用 `0` 测试默认方向
- 然后尝试 `90` 或 `-90`
- 根据实际效果微调角度
- 记录最佳配置值

---

*文档维护者：Claude Sonnet 4.5*
*最后更新：2026-02-04*
