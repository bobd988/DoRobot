#!/usr/bin/env python3
"""实时监控 SO101 主臂的关节值"""

import sys
import os
import time
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

    print("=" * 80)
    print("SO101 主臂关节监控")
    print("=" * 80)
    print(f"\n标定文件中的关节数量: {len(calib_data)}")
    print("\n关节列表:")
    for i, (name, data) in enumerate(calib_data.items(), 1):
        print(f"  {i}. {name:20s} (ID: {data['id']})")
    print("\n" + "=" * 80)
    print("提示: 移动末端夹爪,观察哪个值在变化")
    print("按 Ctrl+C 退出")
    print("=" * 80 + "\n")

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
        print("✓ 已连接到主臂\n")

        # 存储上一次的值,用于检测变化
        prev_values = None

        while True:
            present_pos = bus.sync_read("Present_Position")
            joint_names = list(present_pos.keys())
            joint_values = [val for _motor, val in present_pos.items()]

            # 清屏并显示
            print("\033[H\033[J", end="")  # ANSI 清屏
            print("=" * 80)
            print(f"实时关节值 (共 {len(joint_values)} 个值)")
            print("=" * 80)

            for i, (name, value) in enumerate(zip(joint_names, joint_values)):
                # 检测变化
                change_indicator = ""
                if prev_values is not None:
                    diff = abs(value - prev_values[i])
                    if diff > 0.01:  # 变化超过 0.01 弧度
                        change_indicator = f"  ← 变化: {diff:+.3f}"

                # 转换为度数显示
                degrees = value * 180 / 3.14159
                print(f"  [{i+1}] {name:20s}: {value:+.4f} rad ({degrees:+7.2f}°){change_indicator}")

            print("=" * 80)
            print("提示: 慢慢移动末端夹爪,观察哪个值在变化")
            print("      如果是 [6] gripper 在变化,说明 gripper 是夹爪")
            print("      如果 gripper 不变但其他值变,说明 gripper 可能是 joint_6")

            prev_values = joint_values
            time.sleep(0.1)  # 10Hz 更新

    except KeyboardInterrupt:
        print("\n\n程序已停止")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'bus' in locals():
            bus.disconnect()

if __name__ == "__main__":
    main()
