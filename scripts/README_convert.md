# 数据格式转换工具使用说明

## 功能说明

将当前的Parquet格式数据转换为交付标准的JSONL格式。

## 转换内容

### 输入格式（当前）
```
leader-follower-x5/
├── data/chunk-000/episode_000000.parquet
└── videos/chunk-000/
    ├── observation.images.top/episode_000000.mp4
    └── observation.images.wrist/episode_000000.mp4
```

### 输出格式（交付标准）
```
leader-follower-x5-converted/
├── data/
│   └── episode_000000/
│       ├── meta/
│       │   └── episode_meta.json
│       ├── states/
│       │   └── states.jsonl
│       └── videos/
│           ├── arm_realsense_rgb.mp4
│           └── global_realsense_rgb.mp4
├── meta/
│   └── task_info.json
└── task_desc.json
```

## 使用方法

### 基本用法
```bash
python scripts/convert_to_delivery_format.py
```

### 指定输入输出目录
```bash
python scripts/convert_to_delivery_format.py \
  --input /path/to/input \
  --output /path/to/output \
  --task-name my_task
```

### 参数说明
- `--input, -i`: 输入目录（默认: `/home/dora/DoRobot-vr/dataset/leader-follower-x5`）
- `--output, -o`: 输出目录（默认: `/home/dora/DoRobot-vr/dataset/leader-follower-x5-converted`）
- `--task-name, -t`: 任务名称（默认: `leader_follower_x5`）

## 数据转换说明

### 1. states.jsonl 字段映射

| 交付标准字段 | 来源 | 说明 |
|-------------|------|------|
| `joint_positions` | `observation.state[:6]` | 6个关节位置 |
| `joint_velocities` | 计算得出 | 从相邻帧位置差分计算 |
| `end_effector_pose` | 占位符 | 暂时填充 `[0,0,0,0,0,0]` |
| `gripper_width` | `observation.state[6]` | 夹爪宽度 |
| `gripper_velocity` | 计算得出 | 从相邻帧夹爪值差分计算 |
| `timestamp` | `timestamp` | 时间戳 |

### 2. 视频文件映射

| 原始名称 | 转换后名称 |
|---------|-----------|
| `observation.images.top` | `global_realsense_rgb.mp4` |
| `observation.images.wrist` | `arm_realsense_rgb.mp4` |

### 3. 元数据文件

#### episode_meta.json
```json
{
  "episode_index": 0,
  "start_time": 0.0,
  "end_time": 9.77,
  "frames": 294
}
```

#### task_desc.json
```json
{
  "robot_id": "arx5_leader_follower",
  "task_desc": {
    "task_name": "leader_follower_x5",
    "prompt": "Leader-follower teleoperation...",
    "scoring": "Data quality based on...",
    "task_tag": ["teleoperation", "leader-follower", ...]
  },
  "video_info": {
    "fps": 30,
    "ext": "mp4",
    "encoding": {...}
  }
}
```

#### task_info.json
```json
{
  "task_name": "leader_follower_x5",
  "total_episodes": 1,
  "robot_type": "ARX5",
  "control_mode": "leader-follower",
  "data_format_version": "1.0"
}
```

## 注意事项

### ⚠️ end_effector_pose 字段
当前版本使用占位符 `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]`。

如需真实的末端执行器位姿，需要：
1. 使用机器人URDF模型
2. 实现正运动学计算
3. 或从硬件传感器读取

### ✓ 速度计算
- `joint_velocities` 和 `gripper_velocity` 通过相邻帧差分计算
- 第一帧速度为 0
- 公式: `velocity = (position[t] - position[t-1]) / dt`

### ✓ 批量转换
脚本会自动处理输入目录中的所有episode

## 验证转换结果

转换完成后，可以使用以下命令验证：

```bash
# 查看目录结构
tree /home/dora/DoRobot-vr/dataset/leader-follower-x5-converted/

# 查看states.jsonl前几行
head -n 3 /home/dora/DoRobot-vr/dataset/leader-follower-x5-converted/data/episode_000000/states/states.jsonl

# 查看元数据
cat /home/dora/DoRobot-vr/dataset/leader-follower-x5-converted/task_desc.json
```

## 常见问题

### Q: 转换后原始数据会被删除吗？
A: 不会。转换脚本只读取原始数据，不会修改或删除。

### Q: 可以转换多个episode吗？
A: 可以。脚本会自动查找并转换所有episode。

### Q: 如何添加第三个相机？
A: 修改脚本中的 `video_mapping` 字典，添加新的映射关系。

### Q: 如何实现真实的end_effector_pose？
A: 需要修改脚本，添加正运动学计算。可以使用 `roboticstoolbox` 或 `pybullet` 库。

## 更新日志

- v1.0 (2026-02-03): 初始版本
  - 支持Parquet到JSONL转换
  - 自动计算关节速度和夹爪速度
  - 生成所有必需的元数据文件
