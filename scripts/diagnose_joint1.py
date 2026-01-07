#!/usr/bin/env python3
"""诊断 joint_1 的运动范围和抖动问题"""

import os
import sys
import time
import argparse
from piper_sdk import C_PiperInterface


def enable_arm(piper: C_PiperInterface) -> bool:
    """使能机械臂"""
    enable_flag = all(piper.GetArmEnableStatus())
    if not enable_flag:
        piper.EnablePiper()
        time.sleep(0.5)
    print("✓ 机械臂已使能")
    return True


def get_current_position(piper: C_PiperInterface) -> list[int]:
    """读取当前关节位置"""
    joint = piper.GetArmJointMsgs()
    return [
        joint.joint_state.joint_1.real,
        joint.joint_state.joint_2.real,
        joint.joint_state.joint_3.real,
        joint.joint_state.joint_4.real,
        joint.joint_state.joint_5.real,
        joint.joint_state.joint_6.real,
    ]


def test_joint1_range(piper: C_PiperInterface, speed: int = 20):
    """测试 joint_1 的运动范围"""
    print("\n" + "="*70)
    print("测试 joint_1 运动范围")
    print("="*70)

    # 读取初始位置
    initial_pos = get_current_position(piper)
    print(f"\n初始位置: {[p/1000 for p in initial_pos]}")
    print(f"joint_1 初始位置: {initial_pos[0]/1000:.2f}°")

    # 设置运动速度
    piper.MotionCtrl_2(0x01, 0x01, speed, 0x00)

    # 测试向左转（正方向）
    print(f"\n测试1: 向左转 +20°")
    target_left = initial_pos.copy()
    target_left[0] = initial_pos[0] + 20000  # +20度
    piper.JointCtrl(*target_left)
    time.sleep(3)

    pos_left = get_current_position(piper)
    actual_change_left = (pos_left[0] - initial_pos[0]) / 1000
    print(f"  目标: {target_left[0]/1000:.2f}°")
    print(f"  实际: {pos_left[0]/1000:.2f}°")
    print(f"  变化: {actual_change_left:.2f}° (期望: +20.00°)")

    if abs(actual_change_left - 20) < 2:
        print("  ✓ 向左转正常")
    else:
        print(f"  ✗ 向左转异常 (差异: {abs(actual_change_left - 20):.2f}°)")

    # 返回初始位置
    print(f"\n返回初始位置...")
    piper.JointCtrl(*initial_pos)
    time.sleep(3)

    # 测试向右转（负方向）
    print(f"\n测试2: 向右转 -20°")
    target_right = initial_pos.copy()
    target_right[0] = initial_pos[0] - 20000  # -20度
    piper.JointCtrl(*target_right)
    time.sleep(3)

    pos_right = get_current_position(piper)
    actual_change_right = (pos_right[0] - initial_pos[0]) / 1000
    print(f"  目标: {target_right[0]/1000:.2f}°")
    print(f"  实际: {pos_right[0]/1000:.2f}°")
    print(f"  变化: {actual_change_right:.2f}° (期望: -20.00°)")

    if abs(actual_change_right + 20) < 2:
        print("  ✓ 向右转正常")
    else:
        print(f"  ✗ 向右转异常 (差异: {abs(actual_change_right + 20):.2f}°)")

    # 返回初始位置
    print(f"\n返回初始位置...")
    piper.JointCtrl(*initial_pos)
    time.sleep(3)

    return {
        'left_ok': abs(actual_change_left - 20) < 2,
        'right_ok': abs(actual_change_right + 20) < 2,
        'left_change': actual_change_left,
        'right_change': actual_change_right
    }


def test_joint1_stability(piper: C_PiperInterface, duration: int = 10):
    """测试 joint_1 的稳定性（抖动检测）"""
    print("\n" + "="*70)
    print(f"测试 joint_1 稳定性 (持续 {duration} 秒)")
    print("="*70)

    # 读取初始位置
    initial_pos = get_current_position(piper)

    # 发送保持命令
    piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
    piper.JointCtrl(*initial_pos)

    print(f"\n保持位置: {initial_pos[0]/1000:.2f}°")
    print("监测位置变化...")

    positions = []
    start_time = time.time()

    while time.time() - start_time < duration:
        current = get_current_position(piper)
        positions.append(current[0])
        time.sleep(0.1)

    # 分析抖动
    positions_deg = [p/1000 for p in positions]
    mean_pos = sum(positions_deg) / len(positions_deg)
    max_pos = max(positions_deg)
    min_pos = min(positions_deg)
    range_pos = max_pos - min_pos

    # 计算标准差
    variance = sum((p - mean_pos)**2 for p in positions_deg) / len(positions_deg)
    std_dev = variance ** 0.5

    print(f"\n稳定性分析:")
    print(f"  平均位置: {mean_pos:.3f}°")
    print(f"  最大位置: {max_pos:.3f}°")
    print(f"  最小位置: {min_pos:.3f}°")
    print(f"  位置范围: {range_pos:.3f}°")
    print(f"  标准差: {std_dev:.3f}°")

    # 判断稳定性
    if range_pos < 0.5:
        print("  ✓ 位置非常稳定")
        stability = "excellent"
    elif range_pos < 1.0:
        print("  ✓ 位置稳定")
        stability = "good"
    elif range_pos < 2.0:
        print("  ⚠ 位置轻微抖动")
        stability = "fair"
    else:
        print(f"  ✗ 位置抖动严重 (范围: {range_pos:.3f}°)")
        stability = "poor"

    return {
        'stability': stability,
        'range': range_pos,
        'std_dev': std_dev,
        'mean': mean_pos
    }


def main():
    parser = argparse.ArgumentParser(description="诊断 joint_1 运动范围和抖动问题")
    parser.add_argument(
        "--can-bus",
        type=str,
        default="",
        help="CAN 总线接口 (默认: 从 CAN_BUS 环境变量读取)",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=20,
        help="运动速度百分比 (默认: 20)",
    )
    parser.add_argument(
        "--stability-duration",
        type=int,
        default=10,
        help="稳定性测试持续时间（秒）(默认: 10)",
    )

    args = parser.parse_args()

    can_bus = args.can_bus or os.getenv("CAN_BUS", "can_left")

    print("="*70)
    print("joint_1 诊断工具")
    print("="*70)
    print(f"CAN 总线: {can_bus}")
    print(f"运动速度: {args.speed}%")
    print(f"稳定性测试时长: {args.stability_duration}秒")

    # 初始化
    print(f"\n初始化 Piper 机械臂...")
    piper = C_PiperInterface(can_bus)
    piper.ConnectPort()

    if not enable_arm(piper):
        sys.exit(1)

    # 测试运动范围
    range_result = test_joint1_range(piper, args.speed)

    # 测试稳定性
    stability_result = test_joint1_stability(piper, args.stability_duration)

    # 总结
    print("\n" + "="*70)
    print("诊断总结")
    print("="*70)

    print("\n运动范围测试:")
    print(f"  向左转 (+20°): {'✓ 正常' if range_result['left_ok'] else '✗ 异常'}")
    print(f"    实际变化: {range_result['left_change']:.2f}°")
    print(f"  向右转 (-20°): {'✓ 正常' if range_result['right_ok'] else '✗ 异常'}")
    print(f"    实际变化: {range_result['right_change']:.2f}°")

    print(f"\n稳定性测试:")
    print(f"  稳定性: {stability_result['stability']}")
    print(f"  位置范围: {stability_result['range']:.3f}°")
    print(f"  标准差: {stability_result['std_dev']:.3f}°")

    # 诊断建议
    print("\n诊断建议:")

    if not range_result['left_ok'] and not range_result['right_ok']:
        print("  ✗ 双向运动都有问题 - 可能是电机驱动器故障或机械卡滞")
    elif not range_result['left_ok']:
        print("  ✗ 向左转有问题 - 可能是电机驱动器单向故障或机械阻力")
    elif not range_result['right_ok']:
        print("  ✗ 向右转有问题 - 可能是电机驱动器单向故障或机械阻力")
        print("  建议:")
        print("    1. 断电后手动转动 joint_1，检查是否有机械阻力")
        print("    2. 检查该关节的电源供应是否稳定")
        print("    3. 联系厂商检查电机驱动器")
    else:
        print("  ✓ 运动范围正常")

    if stability_result['stability'] in ['poor', 'fair']:
        print(f"  ⚠ 位置抖动 (范围: {stability_result['range']:.3f}°)")
        print("  可能原因:")
        print("    1. 编码器信号不稳定")
        print("    2. 电源供应不足或有干扰")
        print("    3. PID 控制参数需要调整")
        print("    4. 机械磨损或间隙过大")
    else:
        print("  ✓ 位置稳定")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
