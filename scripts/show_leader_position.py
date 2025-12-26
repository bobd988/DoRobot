#!/usr/bin/env python3
"""显示主臂当前位置，帮助调整到匹配从臂初始位置"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1'))

from motors.zhonglin import ZhonglinMotorsBus
from motors import Motor, MotorNormMode, MotorCalibration

def main():
    port = os.getenv("ARM_LEADER_PORT", "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    calib_file = os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1', '.calibration', 'SO101-leader.json')

    # 读取标定文件
    with open(calib_file, 'r') as f:
        calib_data = json.load(f)

    # 转换为 MotorCalibration 对象
    calibration = {}
    for name, data in calib_data.items():
        calibration[name] = MotorCalibration(
            id=data['id'],
            homing_offset=data['homing_offset'],
            drive_mode=data['drive_mode'],
            range_min=data['range_min'],
            range_max=data['range_max']
        )

    # 创建舵机总线
    motors = {
        "joint_0": Motor(0, "zhonglin", MotorNormMode.RADIANS),
        "joint_1": Motor(1, "zhonglin", MotorNormMode.RADIANS),
        "joint_2": Motor(2, "zhonglin", MotorNormMode.RADIANS),
        "joint_3": Motor(3, "zhonglin", MotorNormMode.RADIANS),
        "joint_4": Motor(4, "zhonglin", MotorNormMode.RADIANS),
        "joint_5": Motor(5, "zhonglin", MotorNormMode.RADIANS),
        "gripper": Motor(6, "zhonglin", MotorNormMode.RADIANS),
    }

    try:
        bus = ZhonglinMotorsBus(port=port, motors=motors, calibration=calibration, baudrate=115200)
        bus.connect()

        print("\n" + "="*70)
        print("主臂当前位置")
        print("="*70)

        # 从臂的目标初始位置（度）
        follower_target = [5.4, 0.0, 0.0, -2.9, 19.7, 23.9]

        print("\n从臂初始位置（目标）：")
        print(f"  {follower_target}")

        # 读取主臂当前位置
        present_pos = bus.sync_read("Present_Position")
        leader_current = []

        print("\n主臂当前位置（弧度 → 度）：")
        for name, value in present_pos.items():
            degrees = value * 180 / 3.14159
            leader_current.append(degrees)
            print(f"  {name:12s}: {value:+.4f} rad = {degrees:+7.2f}°")

        print("\n位置差异（度）：")
        differences = [abs(leader_current[i] - follower_target[i]) for i in range(6)]
        for i, (name, diff) in enumerate(zip(present_pos.keys(), differences)):
            if i < 6:  # 只显示前6个关节，不包括gripper
                status = "✓" if diff < 40 else "✗"
                print(f"  {name:12s}: {diff:7.2f}° {status}")

        max_diff = max(differences)
        print(f"\n最大差异: {max_diff:.2f}°")

        if max_diff < 40:
            print("✓ 位置差异在阈值内，可以启动遥操")
        else:
            print("✗ 位置差异过大，需要调整主臂位置")
            print("\n建议：手动移动主臂，使其接近从臂初始位置")

        print("="*70 + "\n")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'bus' in locals():
            bus.disconnect()

if __name__ == "__main__":
    main()
