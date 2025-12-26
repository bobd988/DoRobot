#!/usr/bin/env python3
"""同步主臂标定，使其在当前姿态下输出与从臂初始位置相同的数值"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1'))

from motors.zhonglin import ZhonglinMotorsBus
from motors import Motor, MotorNormMode, MotorCalibration
import re

def main():
    port = os.getenv("ARM_LEADER_PORT", "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    calib_file = os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1', '.calibration', 'SO101-leader.json')

    # 读取当前标定文件
    with open(calib_file, 'r') as f:
        calib_data = json.load(f)

    # 从臂初始位置（度）
    follower_target = [5.4, 0.0, 0.0, -2.9, 19.7, 23.9]

    # 创建临时标定用于读取当前PWM
    calibration = {}
    for name, data in calib_data.items():
        if name != 'gripper':
            calibration[name] = MotorCalibration(
                id=data['id'],
                homing_offset=data['homing_offset'],
                drive_mode=data['drive_mode'],
                range_min=data['range_min'],
                range_max=data['range_max']
            )

    motors = {
        "joint_0": Motor(0, "zhonglin", MotorNormMode.RADIANS),
        "joint_1": Motor(1, "zhonglin", MotorNormMode.RADIANS),
        "joint_2": Motor(2, "zhonglin", MotorNormMode.RADIANS),
        "joint_3": Motor(3, "zhonglin", MotorNormMode.RADIANS),
        "joint_4": Motor(4, "zhonglin", MotorNormMode.RADIANS),
        "joint_5": Motor(5, "zhonglin", MotorNormMode.RADIANS),
    }

    try:
        bus = ZhonglinMotorsBus(port=port, motors=motors, calibration=calibration, baudrate=115200)
        bus.connect()

        print("\n" + "="*70)
        print("同步主臂标定")
        print("="*70)

        # 读取当前PWM值
        current_pwms = {}
        for name, motor in motors.items():
            response = bus.send_command(f'#{motor.id:03d}PRAD!')
            match = re.search(r'P(\d{4})', response.strip())
            if match:
                current_pwms[name] = int(match.group(1))
            else:
                print(f"错误：无法读取 {name} 的PWM值")
                return

        print("\n当前PWM值：")
        for name, pwm in current_pwms.items():
            print(f"  {name}: {pwm}")

        print("\n计算新的标定参数：")
        print(f"{'关节':<12} {'目标角度':<12} {'当前PWM':<12} {'新homing_offset':<18} {'drive_mode':<12}")
        print("-" * 70)

        new_calibration = {}
        for i, name in enumerate(["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]):
            calib = calib_data[name]
            target_deg = follower_target[i]
            current_pwm = current_pwms[name]
            range_min = calib['range_min']
            range_max = calib['range_max']

            # 处理负角度：使用drive_mode=1来反转输出
            if target_deg < 0:
                drive_mode = 1
                target_deg_abs = abs(target_deg)
            else:
                drive_mode = 0
                target_deg_abs = target_deg

            # 计算目标calibrated_pwm
            target_calibrated_pwm = range_min + (target_deg_abs / 270.0) * (range_max - range_min)

            # 计算新的homing_offset
            new_homing_offset = round(current_pwm - target_calibrated_pwm)

            print(f"{name:<12} {follower_target[i]:>+11.1f}° {current_pwm:>11d} {new_homing_offset:>17d} {drive_mode:>11d}")

            new_calibration[name] = {
                "id": calib['id'],
                "drive_mode": drive_mode,
                "homing_offset": new_homing_offset,
                "range_min": range_min,
                "range_max": range_max
            }

        # 保留gripper的原始标定
        new_calibration['gripper'] = calib_data['gripper']

        print("\n" + "="*70)
        print("保存新标定到文件...")

        with open(calib_file, 'w') as f:
            json.dump(new_calibration, f, indent=4)

        print(f"✓ 标定已保存到: {calib_file}")
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
