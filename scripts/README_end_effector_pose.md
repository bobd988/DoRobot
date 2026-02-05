# end_effector_pose 获取指南

## 📖 什么是 end_effector_pose

**end_effector_pose（末端执行器位姿）** 描述机械臂末端在空间中的**位置**和**姿态**。

### 组成（6个值）

```
[x, y, z, roll, pitch, yaw]
```

| 索引 | 名称 | 含义 | 单位 |
|------|------|------|------|
| 0 | x | 前后方向坐标 | 米 (m) |
| 1 | y | 左右方向坐标 | 米 (m) |
| 2 | z | 上下方向坐标 | 米 (m) |
| 3 | roll | 绕X轴旋转 | 弧度 (rad) |
| 4 | pitch | 绕Y轴旋转 | 弧度 (rad) |
| 5 | yaw | 绕Z轴旋转 | 弧度 (rad) |

### 示例

```python
pose = [0.14, 0.001, 0.156, 0.0, 0.0, 0.0]
```
- 末端位于 (0.14m, 0.001m, 0.156m)
- 姿态为 (0°, 0°, 0°) - 水平朝前

---

## 🔧 获取方法

### 方法1: 正运动学计算（推荐）✅

使用关节角度 + URDF模型计算末端位姿

#### 安装依赖

```bash
# 选项1: ikpy (推荐，轻量级)
pip install ikpy

# 选项2: pybullet (已安装)
# 系统已有，无需安装

# 选项3: roboticstoolbox
pip install roboticstoolbox-python
```

#### 使用FK计算器

```python
from fk_calculator import ForwardKinematicsCalculator

# 初始化
fk = ForwardKinematicsCalculator()

# 计算末端位姿
joint_positions = [0.0, 0.5, -0.5, 0.0, 0.0, 0.0]  # 6个关节角度（弧度）
pose = fk.calculate(joint_positions)

print(pose)  # [x, y, z, roll, pitch, yaw]
# 输出: [0.0428, 0.0010, -0.0659, -0.0000, 1.0000, -0.0000]
```

---

## 🔄 集成到转换脚本

### 更新转换脚本以使用真实FK

修改 `convert_to_delivery_format.py`：

```python
# 在文件开头添加
from fk_calculator import ForwardKinematicsCalculator

# 在 __init__ 方法中初始化
def __init__(self, input_dir: str, output_dir: str, task_name: str = "leader_follower_x5"):
    self.input_dir = Path(input_dir)
    self.output_dir = Path(output_dir)
    self.task_name = task_name

    # 初始化FK计算器
    try:
        self.fk = ForwardKinematicsCalculator()
        self.use_real_fk = True
        print("✓ FK计算器初始化成功")
    except Exception as e:
        print(f"⚠ FK计算器初始化失败: {e}")
        print("  将使用占位符")
        self.use_real_fk = False

# 在 generate_states_jsonl 方法中使用
def generate_states_jsonl(self, df: pd.DataFrame, output_file: Path):
    for i in range(len(df)):
        obs_state = df['observation.state'].iloc[i]

        # 计算末端执行器位姿
        if self.use_real_fk:
            end_effector_pose = self.fk.calculate(obs_state[:6].tolist())
        else:
            end_effector_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        state = {
            "joint_positions": [float(x) for x in obs_state[:6]],
            "joint_velocities": [...],
            "end_effector_pose": end_effector_pose,  # 使用真实FK
            ...
        }
```

---

## 🧪 测试FK计算

### 测试脚本

```bash
python scripts/fk_calculator.py
```

### 预期输出

```
======================================================================
正运动学计算器测试
======================================================================
✓ 使用 pybullet 库进行FK计算

测试配置 1:
  关节角度: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  末端位姿:
    位置 (x, y, z): (0.1400, 0.0010, 0.1563) 米
    姿态 (r, p, y): (-0.0000, 0.0000, 0.0000) 弧度
                    (-0.00°, 0.00°, 0.00°)
```

---

## 📊 运动学库对比

| 库 | 优点 | 缺点 | 推荐度 |
|----|------|------|--------|
| **pybullet** | 已安装，功能强大 | 较重，需要物理引擎 | ⭐⭐⭐⭐ |
| **ikpy** | 轻量级，易用 | 需要安装 | ⭐⭐⭐⭐⭐ |
| **roboticstoolbox** | 功能全面，教学友好 | 依赖多，较重 | ⭐⭐⭐ |

**推荐**: 如果只需要FK，使用 `ikpy`；如果已有pybullet，直接使用。

---

## 🔍 验证FK结果

### 方法1: 可视化检查

```python
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 计算多个配置的末端位置
positions = []
for angle in np.linspace(0, np.pi/2, 10):
    joints = [0, angle, -angle, 0, 0, 0]
    pose = fk.calculate(joints)
    positions.append(pose[:3])  # 只取位置

# 绘制末端轨迹
positions = np.array(positions)
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.plot(positions[:, 0], positions[:, 1], positions[:, 2])
ax.set_xlabel('X (m)')
ax.set_ylabel('Y (m)')
ax.set_zlabel('Z (m)')
plt.show()
```

### 方法2: 与实际测量对比

1. 将机械臂移动到已知位置
2. 记录关节角度
3. 用FK计算末端位姿
4. 用尺子测量实际位置
5. 对比误差（应小于1cm）

---

## ⚠️ 常见问题

### Q: FK计算结果不准确？
A: 检查：
1. URDF模型是否正确
2. 关节角度单位（必须是弧度）
3. 坐标系定义是否一致

### Q: 需要安装哪个库？
A: 系统已有pybullet，可以直接使用。如果想要更轻量级，安装ikpy。

### Q: 如何验证FK是否正确？
A:
1. 零位测试：所有关节为0时，检查末端位置是否合理
2. 单关节测试：只转动一个关节，检查末端轨迹
3. 与实际测量对比

### Q: end_effector_pose 必须提供吗？
A: 根据交付标准，是必需的。如果暂时无法计算，可以先用占位符，但最终应提供真实值。

---

## 📝 下一步

1. **测试FK计算器**: `python scripts/fk_calculator.py`
2. **集成到转换脚本**: 修改 `convert_to_delivery_format.py`
3. **重新转换数据**: 使用真实FK重新生成数据
4. **验证结果**: 检查生成的end_effector_pose是否合理

---

## 📚 参考资料

- [ikpy文档](https://github.com/Phylliade/ikpy)
- [PyBullet文档](https://pybullet.org/)
- [正运动学原理](https://en.wikipedia.org/wiki/Forward_kinematics)
- [DH参数](https://en.wikipedia.org/wiki/Denavit%E2%80%93Hartenberg_parameters)
