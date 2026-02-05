#!/usr/bin/env python3
"""测试适配器的数据转换"""

import numpy as np

# 模拟主臂输出的弧度值
test_cases = [
    # [joint0, joint1, joint2, joint3, joint4, joint5, gripper]
    [-0.016, 1.660, -1.437, -0.695, 0.016, -0.001, -0.175],  # 实际输出
    [0, 0, 0, 0, 0, 0, 0],  # 零位
    [1.57, 0, 0, 0, 0, 0, 0.5],  # 90度 + 夹爪张开
    [-1.57, 0, 0, 0, 0, 0, -0.5],  # -90度 + 夹爪闭合
]

print("=" * 80)
print("适配器数据转换测试")
print("=" * 80)
print()

for i, joint_radians in enumerate(test_cases):
    print(f"测试用例 {i+1}:")
    print(f"  输入 (弧度): {[f'{x:.3f}' for x in joint_radians]}")

    # 前6个关节：弧度 -> 度数
    joint_degrees = [np.rad2deg(joint_radians[j]) for j in range(6)]

    # 夹爪：弧度 -> 0-100
    gripper_rad = joint_radians[6]
    gripper_range = 0.5
    gripper_value = ((gripper_rad + gripper_range) / (2 * gripper_range)) * 100
    gripper_value = max(0, min(100, gripper_value))

    print(f"  输出 (度数): {[f'{x:.1f}' for x in joint_degrees]}")
    print(f"  夹爪: {gripper_rad:.3f} rad -> {gripper_value:.1f}")
    print()

print("=" * 80)
print("分析:")
print("=" * 80)
print("1. 关节角度范围: 弧度值直接转换为度数")
print("2. 夹爪范围: -0.5 rad (闭合) -> 0, 0 rad (中间) -> 50, +0.5 rad (张开) -> 100")
print()
