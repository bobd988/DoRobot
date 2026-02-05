# Leader-Follower 底座抖动问题分析

## 问题描述
在实施90度底座旋转后，机械臂底座出现抖动现象。

## 当前配置

### 1. 底座旋转设置
- **旋转偏移量**: 90度（顺时针）
- **配置位置**: `operating_platform/teleop_vr/leader_follower_adapter.py:45`
- **环境变量**: `BASE_ROTATION_OFFSET=90`

```python
base_rotation_offset = float(os.getenv("BASE_ROTATION_OFFSET", "90"))
```

### 2. 消抖设置

#### 2.1 死区阈值（Dead-band Threshold）
**位置**: `operating_platform/teleop_vr/leader_follower_adapter.py:50-57`

```python
deadband_thresholds = [
    0.8,  # joint_0 (基座) - 与其他关节保持一致，避免小范围运动时卡顿
    0.8,  # joint_1 - 适中死区，平衡灵敏度和稳定性
    0.8,  # joint_2
    0.8,  # joint_3
    0.8,  # joint_4
    0.8,  # joint_5
]
```

**说明**:
- 所有关节（包括基座joint_0）的死区阈值均为 **0.8度**
- 小于0.8度的变化会被忽略，使用上一次的值
- 死区过滤在EMA平滑之后应用

#### 2.2 EMA平滑滤波（Exponential Moving Average）
**位置**: `operating_platform/teleop_vr/leader_follower_adapter.py:32-36`

```python
ema_alpha = float(os.getenv("EMA_ALPHA", "0.2"))  # 默认0.2
```

**说明**:
- EMA系数: **0.2**
- 公式: `new_ema = alpha * current + (1 - alpha) * old_ema`
- alpha=0.2 表示新值权重20%，历史值权重80%
- 较小的alpha值产生更强的平滑效果，但响应会变慢
- EMA平滑在死区过滤之前应用

### 3. 运动范围限制

#### 3.1 主臂（Leader Arm）- Feetech STS3215
**舵机型号**: Feetech STS3215
**分辨率**: 4096步（0-4095）
**理论范围**: 0-360度（完整旋转）

**配置位置**: `operating_platform/robot/robots/configs.py:729-745`

```python
leader_arms: dict[str, MotorsBusConfig] = field(
    default_factory=lambda: {
        "main": FeetechMotorsBusConfig(
            port="/dev/ttyACM0",
            motors={
                "joint_0": [1, "sts3215"],  # 基座
                "joint_1": [2, "sts3215"],
                "joint_2": [3, "sts3215"],
                "joint_3": [4, "sts3215"],
                "joint_4": [5, "sts3215"],
                "joint_5": [6, "sts3215"],
                "gripper": [7, "sts3215"],
            },
        ),
    }
)
```

**实际使用范围**:
- 根据机械结构限制，实际可用范围可能小于360度
- 需要通过实际测试确定安全工作范围

#### 3.2 从臂（Follower Arm）- ARX X5
**机械臂型号**: ARX X5
**URDF文件**: `operating_platform/teleop_vr/x5_kinematics_only.urdf`

**关节限制**（单位：弧度）:

| 关节 | 下限（rad） | 上限（rad） | 下限（度） | 上限（度） | 范围（度） |
|------|------------|------------|-----------|-----------|-----------|
| joint1 (基座) | -1.57 | 1.57 | -90° | 90° | **180°** |
| joint2 | -0.1 | 3.6 | -5.7° | 206.3° | 212° |
| joint3 | -0.1 | 3.0 | -5.7° | 171.9° | 177.6° |
| joint4 | -1.29 | 1.29 | -73.9° | 73.9° | 147.8° |
| joint5 | -1.48 | 1.48 | -84.8° | 84.8° | 169.6° |
| joint6 | -1.74 | 1.74 | -99.7° | 99.7° | 199.4° |

**关键发现**:
- **ARX X5 基座（joint1）的运动范围仅为 ±90度（共180度）**
- 这是一个重要的限制因素

## 问题分析

### 根本原因（已确认）

**严重程度**: 🔴 **关键**

ARX X5 基座（joint1）的软件限位设置过于保守：

- **机械限位**：-150° 到 +180°（共330度范围）
- **原URDF软件限位**：-90° 到 +90°（共180度）- **过于保守！**
- **主臂范围**：可以转180度

**问题表现**：
- 主臂范围：假设 -90° 到 +90°（180度）
- 加上90度偏移：从臂需要工作在 0° 到 +180°
- 机械上完全可行（在 -150° 到 +180° 范围内）
- 但会触碰到软件限位（90度），导致IK求解失败或限位保护触发，产生抖动

**结论**：软件限位不应该限制在 ±90°，应该接近机械限位范围。

### 可能的抖动原因（已过时）

#### 1. 运动范围冲突
**严重程度**: ⚠️ **高**

- **主臂（Feetech STS3215）**: 理论上可以360度旋转
- **从臂（ARX X5 joint1）**: 只能在 -90° 到 +90° 范围内运动（共180度）
- **90度偏移的影响**:
  - 如果主臂的零位对应从臂的0度
  - 加上90度偏移后，从臂需要工作在 90度 附近
  - 这已经接近从臂的上限（90度）
  - 任何向正方向的运动都可能触碰到限位

**示例场景**:
```
主臂位置: 10度
加上偏移: 10 + 90 = 100度
从臂限制: 最大只能到 90度
结果: 超出范围，可能导致抖动或限位保护
```

#### 2. 死区阈值不足
**严重程度**: ⚠️ **中**

- 当前基座死区: **0.8度**
- Feetech STS3215 舵机可能存在读数噪声
- 在接近限位时，即使0.8度的变化也可能导致频繁触碰限位
- 建议: 对于基座关节，可以考虑增大死区到 **2.0-3.0度**

#### 3. EMA平滑系数
**严重程度**: ⚠️ **低**

- 当前EMA alpha: **0.2**
- 这个值已经提供了较强的平滑效果（80%历史值权重）
- 如果需要更强的平滑，可以降低到 **0.1-0.15**
- 但这会降低响应速度

## 解决方案（已实施）

### ✅ 方案：修改URDF软件限位（已完成）
**优先级**: 🔴 **最高** - **已实施**

**问题根源**：URDF文件中joint1的软件限位（±90°）远小于机械限位（-150° 到 +180°），导致90度偏移后触碰软件限位。

**解决方法**：修改 `operating_platform/teleop_vr/x5_kinematics_only.urdf` 中joint1的限位：

```xml
<!-- 修改前 -->
<limit lower="-1.57" upper="1.57" effort="100" velocity="1000"/>

<!-- 修改后 -->
<!-- 机械限位: -150° to +180° (-2.618 to +3.142 rad) -->
<!-- 软件限位设置为略小于机械限位，留安全余量 -->
<limit lower="-2.5" upper="3.0" effort="100" velocity="1000"/>
```

**修改说明**：
- 下限：-2.5 rad ≈ -143°（机械限位 -150°，留7°余量）
- 上限：+3.0 rad ≈ +172°（机械限位 +180°，留8°余量）
- 这样90度偏移后，从臂可以在 0° 到 +180° 范围内自由工作

**预期效果**：
- 完全消除因触碰软件限位导致的抖动
- 保持90度偏移配置不变
- 不需要修改死区或EMA参数

### 备选方案（如果仍有抖动）
**优先级**: 🔴 **最高**

由于ARX X5基座只能在 -90° 到 +90° 范围内运动，90度的偏移会导致工作范围严重受限。

**建议调整**:
- 将偏移从 90度 改为 **0度** 或 **±45度**
- 这样可以确保从臂在整个工作过程中都有足够的运动余量

**修改位置**: `operating_platform/teleop_vr/dora_leader_follower_x5.yml`
```yaml
env:
  BASE_ROTATION_OFFSET: "0"    # 或 "45" / "-45"
  ENABLE_ZERO_ALIGN: "true"
  ZERO_ALIGN_DELAY: "10"
  EMA_ALPHA: "0.2"
```

### 方案2: 增大基座死区阈值
**优先级**: 🟡 **高**

如果必须保持90度偏移，可以增大基座的死区阈值来减少抖动。

**修改位置**: `operating_platform/teleop_vr/leader_follower_adapter.py:50-57`
```python
deadband_thresholds = [
    2.5,  # joint_0 (基座) - 增大死区以减少抖动
    0.8,  # joint_1
    0.8,  # joint_2
    0.8,  # joint_3
    0.8,  # joint_4
    0.8,  # joint_5
]
```

**建议值**: 2.0 - 3.0 度

### 方案3: 增强EMA平滑
**优先级**: 🟢 **中**

降低EMA alpha值以获得更强的平滑效果。

**修改位置**: `operating_platform/teleop_vr/dora_leader_follower_x5.yml`
```yaml
env:
  EMA_ALPHA: "0.1"  # 从0.2降低到0.1，增强平滑
```

**注意**: 这会降低响应速度

### 方案4: 添加软限位检查
**优先级**: 🟢 **中**

在adapter中添加软限位检查，防止发送超出范围的命令。

**实现位置**: `operating_platform/teleop_vr/leader_follower_adapter.py`

```python
# ARX X5 关节限制（度数）
JOINT_LIMITS = [
    (-90, 90),    # joint_0 基座
    (-5.7, 206.3),  # joint_1
    (-5.7, 171.9),  # joint_2
    (-73.9, 73.9),  # joint_3
    (-84.8, 84.8),  # joint_4
    (-99.7, 99.7),  # joint_5
]

# 在发送命令前检查并限制
for i in range(6):
    lower, upper = JOINT_LIMITS[i]
    joint_degrees[i] = max(lower, min(upper, joint_degrees[i]))
```

## 测试步骤

### 1. 验证当前运动范围
```bash
# 启动系统
cd /home/dora/DoRobot-vr
bash operating_platform/teleop_vr/start_leader_follower.sh

# 观察日志中的关节角度
# 特别关注 joint_0 的值是否接近或超过 ±90度
```

### 2. 测试不同偏移值
```bash
# 修改配置文件中的 BASE_ROTATION_OFFSET
# 测试 0, 45, -45 等不同值
# 观察抖动是否改善
```

### 3. 调整死区阈值
```bash
# 修改 leader_follower_adapter.py 中的 deadband_thresholds[0]
# 从 0.8 逐步增加到 2.0, 2.5, 3.0
# 观察抖动改善情况
```

## 相关文件

1. **配置文件**:
   - `operating_platform/teleop_vr/dora_leader_follower_x5.yml` - DORA配置
   - `operating_platform/robot/robots/configs.py` - 机器人配置

2. **核心代码**:
   - `operating_platform/teleop_vr/leader_follower_adapter.py` - 主从适配器
   - `operating_platform/teleop_vr/robot_driver_arx_x5.py` - ARX X5驱动

3. **URDF文件**:
   - `operating_platform/teleop_vr/x5_kinematics_only.urdf` - ARX X5运动学模型

4. **文档**:
   - `docs/Leader-Follower底座旋转配置.md` - 底座旋转配置说明

## 总结

**核心问题**: ARX X5基座的运动范围（±90度）与90度旋转偏移不兼容，导致工作范围严重受限，容易触碰限位而产生抖动。

**推荐方案**:
1. **首选**: 将底座旋转偏移调整为0度或±45度
2. **备选**: 如果必须保持90度偏移，则增大基座死区阈值到2.5-3.0度

**下一步行动**:
1. 测试当前系统，记录joint_0的实际运动范围
2. 根据测试结果选择合适的偏移值
3. 调整死区阈值和EMA参数进行微调
