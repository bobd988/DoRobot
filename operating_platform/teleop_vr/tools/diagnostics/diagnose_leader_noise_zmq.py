#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主臂关节噪声诊断工具（简化版）
通过DORA dataflow读取主臂数据，分析噪声水平
"""

import sys
import time
import json
import numpy as np
from collections import deque
import zmq

def main():
    print("=" * 60)
    print("主臂关节噪声诊断工具")
    print("=" * 60)
    print()
    print("说明：")
    print("  - 请先启动 DORA dataflow")
    print("  - 保持主臂静止不动")
    print("  - 观察各关节读数的波动范围")
    print("  - 按 Ctrl+C 停止")
    print()
    print("=" * 60)
    print()

    # ZeroMQ配置
    SOCKET_JOINT = "ipc:///tmp/dora-zeromq-leader-follower-joint"

    print(f"连接到 ZeroMQ socket: {SOCKET_JOINT}")

    # 创建ZeroMQ订阅者
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(SOCKET_JOINT)
    socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5秒超时
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("等待数据...")
    print()

    # 为每个关节维护历史数据
    history_size = 100
    joint_histories = [deque(maxlen=history_size) for _ in range(6)]

    sample_count = 0
    start_time = time.time()

    try:
        while True:
            try:
                # 接收数据
                message_parts = socket.recv_multipart()
                if len(message_parts) < 2:
                    continue

                event_id = message_parts[0].decode('utf-8')

                # 只处理主臂数据
                if event_id != "main_leader_joint":
                    continue

                # 解析数据
                buffer_bytes = message_parts[1]
                if len(buffer_bytes) % 4 != 0:
                    continue

                joint_radians = np.frombuffer(buffer_bytes, dtype=np.float32).tolist()

                if len(joint_radians) < 6:
                    continue

                # 转换为度数
                joint_degrees = [np.rad2deg(rad) for rad in joint_radians[:6]]

                # 记录历史
                for i in range(6):
                    joint_histories[i].append(joint_degrees[i])

                sample_count += 1

                # 每10个样本打印一次
                if sample_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"\n采样次数: {sample_count}  运行时间: {elapsed:.1f}s  采样率: {sample_count/elapsed:.1f} Hz")
                    print("-" * 70)
                    print(f"{'关节':<8} {'当前值':<10} {'平均值':<10} {'标准差':<10} {'范围':<15}")
                    print("-" * 70)

                    for i in range(6):
                        if len(joint_histories[i]) > 0:
                            current = joint_degrees[i]
                            mean = np.mean(joint_histories[i])
                            std = np.std(joint_histories[i])
                            min_val = np.min(joint_histories[i])
                            max_val = np.max(joint_histories[i])
                            range_val = max_val - min_val

                            print(f"joint_{i}  {current:>8.2f}°  {mean:>8.2f}°  {std:>8.3f}°  {min_val:>6.2f}~{max_val:>6.2f}° ({range_val:.2f}°)")

                    print("-" * 70)
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
                            recommended_deadband = max(0.5, std * 3)
                            print(f"  joint_{i}: {recommended_deadband:.1f}°")

            except zmq.Again:
                print("等待数据超时，请确保DORA dataflow正在运行...")
                time.sleep(1)

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
            print("-" * 70)
            print(f"{'关节':<8} {'平均值':<10} {'标准差':<10} {'最大范围':<15}")
            print("-" * 70)

            for i in range(6):
                if len(joint_histories[i]) > 0:
                    mean = np.mean(joint_histories[i])
                    std = np.std(joint_histories[i])
                    min_val = np.min(joint_histories[i])
                    max_val = np.max(joint_histories[i])
                    range_val = max_val - min_val

                    print(f"joint_{i}  {mean:>8.2f}°  {std:>8.3f}°  {range_val:>8.2f}°")

            print("-" * 70)
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
        socket.close()
        context.term()
        print()
        print("连接已关闭")


if __name__ == "__main__":
    main()
