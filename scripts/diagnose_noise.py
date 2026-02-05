#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主臂关节实时监测工具
显示每个关节的当前值和变化量
"""

import sys
import time
import numpy as np

try:
    from scservo_sdk import *
except ImportError:
    print("错误: 无法导入 scservo_sdk")
    print("请安装: pip install scservo-sdk")
    sys.exit(1)

def main():
    print("=" * 80)
    print("主臂关节实时监测工具")
    print("=" * 80)
    print()
    print("说明：")
    print("  - 实时显示每个关节的当前值和变化量")
    print("  - 移动主臂观察变化")
    print("  - 按 Ctrl+C 停止")
    print()
    print("=" * 80)
    print()

    # 配置
    DEVICENAME = '/dev/ttyACM0'
    BAUDRATE = 1000000
    PROTOCOL_VERSION = 0
    ADDR_PRESENT_POSITION = 56

    # 初始化
    portHandler = PortHandler(DEVICENAME)
    packetHandler = PacketHandler(PROTOCOL_VERSION)

    # 打开端口
    if not portHandler.openPort():
        print(f"✗ 无法打开端口: {DEVICENAME}")
        print("  请检查:")
        print("  1. 设备是否连接")
        print("  2. 权限: sudo chmod 777 /dev/ttyACM0")
        return

    print(f"✓ 端口已打开: {DEVICENAME}")

    # 设置波特率
    if not portHandler.setBaudRate(BAUDRATE):
        print(f"✗ 无法设置波特率: {BAUDRATE}")
        portHandler.closePort()
        return

    print(f"✓ 波特率已设置: {BAUDRATE}")
    print()
    print("开始监测...")
    print("移动主臂观察变化量！")
    print()

    # 上一次的位置
    last_positions = None
    sample_count = 0
    start_time = time.time()

    # 统计信息
    max_deltas = [0.0] * 6  # 记录最大变化量

    try:
        # 清屏并打印表头
        print("\033[2J\033[H")  # 清屏并移动光标到左上角

        while True:
            # 读取6个关节的位置
            joint_positions = []
            read_success = True

            for motor_id in range(1, 7):
                position, result, error = packetHandler.read2ByteTxRx(
                    portHandler, motor_id, ADDR_PRESENT_POSITION
                )

                if result != COMM_SUCCESS:
                    read_success = False
                    break

                # 转换为度数
                degrees = (position / 4095.0) * 360.0
                if degrees > 180:
                    degrees -= 360

                joint_positions.append(degrees)

            if not read_success or len(joint_positions) < 6:
                continue

            sample_count += 1

            # 计算变化量
            deltas = [0.0] * 6
            if last_positions is not None:
                for i in range(6):
                    deltas[i] = joint_positions[i] - last_positions[i]
                    # 更新最大变化量
                    if abs(deltas[i]) > max_deltas[i]:
                        max_deltas[i] = abs(deltas[i])

            # 每次都更新显示
            elapsed = time.time() - start_time

            # 移动光标到开始位置
            print("\033[H")

            print("=" * 80)
            print(f"主臂关节实时监测  |  样本: {sample_count}  |  运行时间: {elapsed:.1f}s  |  频率: {sample_count/elapsed:.1f}Hz")
            print("=" * 80)
            print()
            print(f"{'关节':<8} {'当前值':<12} {'变化量':<12} {'最大变化':<12} {'状态':<10}")
            print("-" * 80)

            for i in range(6):
                current = joint_positions[i]
                delta = deltas[i]
                max_delta = max_deltas[i]

                # 根据变化量显示状态
                if abs(delta) < 0.1:
                    status = "静止"
                elif abs(delta) < 1.0:
                    status = "微动"
                elif abs(delta) < 5.0:
                    status = "移动"
                else:
                    status = "快速移动"

                # 变化量用颜色标识
                if abs(delta) < 0.5:
                    delta_str = f"{delta:>+8.3f}°"
                elif abs(delta) < 2.0:
                    delta_str = f"\033[33m{delta:>+8.3f}°\033[0m"  # 黄色
                else:
                    delta_str = f"\033[31m{delta:>+8.3f}°\033[0m"  # 红色

                print(f"joint_{i}  {current:>9.2f}°  {delta_str}  {max_delta:>9.3f}°  {status}")

            print("-" * 80)
            print()
            print("说明:")
            print("  - 变化量 = 当前值 - 上一次值")
            print("  - 黄色: 变化 0.5-2.0°  红色: 变化 >2.0°")
            print("  - 最大变化: 记录到的最大单次变化量")
            print()
            print("按 Ctrl+C 停止监测")
            print()

            # 保存当前位置
            last_positions = joint_positions.copy()

            # 控制采样频率（20Hz）
            time.sleep(0.05)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("监测停止")
        print("=" * 80)
        print()
        print("统计摘要:")
        print("-" * 80)
        print(f"{'关节':<8} {'最大单次变化':<15}")
        print("-" * 80)
        for i in range(6):
            print(f"joint_{i}  {max_deltas[i]:>12.3f}°")
        print("-" * 80)
        print()
        print("建议:")
        print("  - 如果静止时变化量 >0.5°，说明有噪声")
        print("  - 如果移动时变化量 <1.0°，说明响应慢或死区太大")
        print("  - 理想情况：静止时变化量接近0，移动时变化量>1.0°")

    finally:
        portHandler.closePort()
        print()
        print("端口已关闭")


if __name__ == "__main__":
    main()
