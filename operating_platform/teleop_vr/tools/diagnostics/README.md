# 诊断工具 (Diagnostics Tools)

本目录包含用于诊断和调试系统问题的工具脚本。

## 工具列表

### 📷 相机诊断
- **`diagnose_camera_connection.py`** - 诊断 RealSense 相机连接问题
  - 检测连接的相机设备
  - 验证序列号配置
  - 测试相机数据流

### 🤖 机械臂诊断
- **`diagnose_robot_movement.py`** - 诊断机械臂运动问题
  - 检查关节运动范围
  - 验证命令响应
  - 测试运动平滑度

- **`diagnose_leader_noise.py`** - 诊断 Leader 机械臂噪声问题
  - 检测关节抖动
  - 分析噪声来源
  - 测试滤波效果

- **`diagnose_leader_noise_zmq.py`** - 通过 ZeroMQ 诊断 Leader 噪声
  - 实时监控数据流
  - 分析传输延迟
  - 检测数据丢失

### 🎮 VR 控制诊断
- **`diagnose_grip_press.py`** - 诊断 VR 握把按键问题
  - 测试握把响应
  - 检测按键延迟
  - 验证事件触发

- **`diagnose_mapping.py`** - 诊断坐标映射问题
  - 验证坐标转换
  - 检查映射精度
  - 测试边界情况

## 使用方法

### 基本用法

```bash
# 激活环境
source ~/miniconda3/bin/activate dorobot

# 运行诊断工具
python tools/diagnostics/diagnose_camera_connection.py
```

### 常见诊断流程

#### 1. 相机无法连接
```bash
python tools/diagnostics/diagnose_camera_connection.py
```

#### 2. Leader 机械臂抖动
```bash
python tools/diagnostics/diagnose_leader_noise.py
```

#### 3. VR 握把无响应
```bash
python tools/diagnostics/diagnose_grip_press.py
```

#### 4. 坐标映射不准确
```bash
python tools/diagnostics/diagnose_mapping.py
```

## 注意事项

- 运行诊断工具前，确保相关硬件已连接
- 某些工具需要 DORA 数据流正在运行
- 诊断结果会输出到终端，注意查看错误信息

## 相关文档

- [系统配置总结](../../docs/系统配置总结-20260205-最终版.md)
- [数据录制错误排查指南](../../docs/数据录制错误排查指南.md)
