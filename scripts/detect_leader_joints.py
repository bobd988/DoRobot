#!/usr/bin/env python3
"""检测主臂关节数量"""

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

    print(f"标定文件中的关节数量: {len(calib_data)}")
    print("\n关节列表:")
    for i, (name, data) in enumerate(calib_data.items(), 1):
        print(f"  {i}. {name:20s} (ID: {data['id']})")

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
        "joint_6": Motor(0, "zhonglin", MotorNormMode.RADIANS),
        "shoulder_pan": Motor(1, "zhonglin", MotorNormMode.RADIANS),
        "shoulder_lift": Motor(2, "zhonglin", MotorNormMode.RADIANS),
        "elbow_flex": Motor(3, "zhonglin", MotorNormMode.RADIANS),
        "wrist_flex": Motor(4, "zhonglin", MotorNormMode.RADIANS),
        "wrist_roll": Motor(5, "zhonglin", MotorNormMode.RADIANS),
        "gripper": Motor(6, "zhonglin", MotorNormMode.RADIANS),
    }

    try:
        bus = ZhonglinMotorsBus(port=port, motors=motors, calibration=calibration, baudrate=115200)
        bus.connect()
        print("\n✓ 已连接到主臂")

        # 读取一次关节位置
        present_pos = bus.sync_read("Present_Position")
        print(f"\n实际检测到的关节数量: {len(present_pos)}")
        print("\n当前关节位置:")
        for name, value in present_pos.items():
            degrees = value * 180 / 3.14159
            print(f"  {name:20s}: {value:+.4f} rad ({degrees:+7.2f}°)")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'bus' in locals():
            bus.disconnect()

if __name__ == "__main__":
    main()
