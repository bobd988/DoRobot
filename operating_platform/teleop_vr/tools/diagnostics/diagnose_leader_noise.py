#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主臂关节噪声诊断工具
实时监测主臂各关节的读数，分析噪声水平
"""

import sys
import time
import numpy as np
from collections import deque

# 添加路径
sys.path.insert(0, '/home/dora/DoRobot/operating_platform/robot/components/arm_normal_so101_v1')

from motors.motors_bus import MotorsBus
from motors.feetech.feetech import FeetechMotorsBus

def main():
    print("=" * 60)
    print("主臂关节噪声诊断工具")
    print("=" * 60)
    print()
    print("说明：")
    print("  - 保持主臂静止不动")
    print("  - 观察各关节读数的波动范围")
    print("  - 按 Ctrl+C 停止")
    print()
    print("=" * 60)
    print()

    # 配置主臂
    port = "/dev/ttyACM0"
    motors_config = {
        "joint_0": [1, "sts3215"],
        "joint_1": [2, "sts3215"],
        "joint_2": [3, "sts3215"],
        "joint_3": [4, "sts3215"],
        "joint_4": [5, "sts3215"],
        "joint_5": [6, "sts3215"],
        "gripper": [7, "sts3215"],
    }

    print(f"连接主臂: {port}")
    try:
        bus = FeetechMotorsBus(port=port, motors=motors_config)
        bus.connect()
        print("✓ 主臂连接成功")
    except Exception as e:
        print(f"✗ 主臂连接失败: {e}")
        return

    print()
    print("开始采集数据...")
    print()

    # 为每个关节维护历史数据（用于计算统计信息）
    history_size = 100  # 保留最近100个读数
    joint_histories = [deque(maxlen=history_size) for _ in range(6)]

    sample_count = 0
    start_time = time.time()

    try:
        while True:
            # 读取关节位置
            positions = bus.read("Present_Position")

            # 转换为度数
            joint_degrees = []
            for i, (name, pos) in enumerate(positions.items()):
                if i >= 6:  # 只处理前6个关节
                    break
                # 弧度转度数
                deg = np.rad2deg(pos)
                joint_degrees.append(deg)
                joint_histories[i].append(deg)

            sample_count += 1

            # 每10个样本打印一次统计信息
            if sample_count % 10 == 0:
                elapsed = time.time() - start_time
                print(f"\n采样次数: {sample_count}  运行时间: {elapsed:.1f}s")
                print("-" * 60)
                print(f"{'关节':<8} {'当前值':<10} {'平均值':<10} {'标准差':<10} {'范围':<15}")
                print("-" * 60)

                for i in range(6):
                    if len(joint_histories[i]) > 0:
                        current = joint_degrees[i]
                        mean = np.mean(joint_histories[i])
                        std = np.std(joint_histories[i])
                        min_val = np.min(joint_histories[i])
                        max_val = np.max(joint_histories[i])
                        range_val = max_val - min_val

                        print(f"joint_{i}  {current:>8.2f}°  {mean:>8.2f}°  {std:>8.3f}°  {min_val:>6.2f}~{max_val:>6.2f}° ({range_val:.2f}°)")

                print("-" * 60)
                print()
                print("噪声分析:")
                for i in range(6):
                    if len(joint_histories[i]) > 0:
                        std = np.std(joint_histories[i])
                        range_val = np.max(joint_histories[i]) - np.min(joint_histories[i])

                        # 评估噪声水平
                        if std < 0.3:
                            level = "很小"
                        elif std < 0.5:
                            level = "小"
                        elif std < 1.0:
                            level = "中等"
                        elif std < 2.0:
                            level = "大"
                        else:
                            level = "很大"

                        print(f"  joint_{i}: 标准差={std:.3f}°, 范围={range_val:.2f}°, 噪声水平={level}")

                print()
                print("建议的死区阈值（基于3倍标准差）:")
                for i in range(6):
                    if len(joint_histories[i]) > 0:
                        std = np.std(joint_histories[i])
                        recommended_deadband = max(0.5, std * 3)  # 至少0.5度
                        print(f"  joint_{i}: {recommended_deadband:.1f}°")

            # 控制采样频率（20Hz）
            time.sleep(0.05)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 60)
        print("停止采集")
        print("=" * 60)
        print()

        # 最终统计
        if sample_count > 0:
            print("最终统计结果:")
            print("-" * 60)
            print(f"{'关节':<8} {'平均值':<10} {'标准差':<10} {'最大范围':<15}")
            print("-" * 60)

            for i in range(6):
                if len(joint_histories[i]) > 0:
                    mean = np.mean(joint_histories[i])
                    std = np.std(joint_histories[i])
                    min_val = np.min(joint_histories[i])
                    max_val = np.max(joint_histories[i])
                    range_val = max_val - min_val

                    print(f"joint_{i}  {mean:>8.2f}°  {std:>8.3f}°  {range_val:>8.2f}°")

            print("-" * 60)
            print()
            print("推荐配置:")
            print()
            print("deadband_thresholds = [")
            for i in range(6):
                if len(joint_histories[i]) > 0:
                    std = np.std(joint_histories[i])
                    recommended = max(0.5, std * 3)
                    recommended = round(recommended * 2) / 2  # 四舍五入到0.5
                    print(f"    {recommended:.1f},  # joint_{i}")
            print("]")

    finally:
        bus.disconnect()
        print()
        print("主臂已断开")


if __name__ == "__main__":
    main()
