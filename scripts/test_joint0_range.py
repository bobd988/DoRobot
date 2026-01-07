#!/usr/bin/env python3
"""测试 joint_0 的实际物理运动范围"""

import sys
import os
sys.path.insert(0, 'operating_platform/robot/components/arm_normal_so101_v1')

from motors.zhonglin import ZhonglinMotorsBus
from motors import Motor, MotorNormMode

port = os.getenv("ARM_LEADER_PORT", "/dev/ttyUSB0")

print("="*70)
print("joint_0 物理范围测试")
print("="*70)
print("\n这个测试将读取 joint_0 在不同位置的原始 PWM 值")
print("请手动移动 joint_0 并观察 PWM 变化\n")

motors = {'joint_0': Motor(0, 'zhonglin', MotorNormMode.RADIANS)}
bus = ZhonglinMotorsBus(port=port, motors=motors, calibration={}, baudrate=115200)
bus.connect()

print("指令:")
print("  1. 将 joint_0 转到最左边（或最右边）的极限位置")
print("  2. 记录 PWM 值")
print("  3. 将 joint_0 转到另一边的极限位置")
print("  4. 记录 PWM 值")
print("  5. 按 Ctrl+C 退出\n")
print("-"*70)

try:
    import time
    while True:
        # 读取原始位置（不应用任何标定）
        pos = bus.sync_read('Present_Position')

        # 从调试输出中提取 PWM 值
        # 格式: [Zhonglin Debug] joint_0: raw=XX.XX° (PWM=XXXX)
        print(f"\r当前读数: {pos}", end='', flush=True)
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\n\n" + "="*70)
    print("测试结束")
    print("="*70)
    print("\n请根据观察到的 PWM 范围判断:")
    print("  - 如果 PWM 范围远大于 1221-1419，说明需要重新标定")
    print("  - 如果 PWM 范围接近 1221-1419，说明这就是物理极限")

finally:
    bus.disconnect()
