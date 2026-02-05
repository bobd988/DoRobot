#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧率诊断工具
检查数据采集时的实际帧率 vs 记录的帧率
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

def diagnose_framerate(parquet_file: str):
    """诊断帧率问题"""
    print("=" * 70)
    print("帧率诊断工具")
    print("=" * 70)

    # 读取数据
    table = pq.read_table(parquet_file)
    df = table.to_pandas()

    timestamps = df['timestamp'].values

    print(f"\n数据文件: {parquet_file}")
    print(f"总帧数: {len(timestamps)}")
    print(f"\n时间戳分析:")
    print(f"  起始: {timestamps[0]:.4f}s")
    print(f"  结束: {timestamps[-1]:.4f}s")
    print(f"  记录时长: {timestamps[-1] - timestamps[0]:.4f}s")

    # 计算理论帧率
    if len(timestamps) > 1:
        avg_interval = (timestamps[-1] - timestamps[0]) / (len(timestamps) - 1)
        recorded_fps = 1 / avg_interval
        print(f"  平均帧间隔: {avg_interval:.4f}s")
        print(f"  记录的帧率: {recorded_fps:.2f} fps")

    print("\n" + "=" * 70)
    print("问题分析:")
    print("=" * 70)

    print("""
当前系统使用 frame_index / fps 来计算时间戳，而不是真实的系统时间。

这意味着：
  • 时间戳总是理想的等间隔（如 30fps 时为 0.0333s）
  • 但实际采集可能慢于这个速度
  • 导致视频播放比实际运动快

示例：
  如果系统实际只能达到 15fps：
    - 记录的时间戳: 0, 0.033, 0.066, 0.100, ... (假设30fps)
    - 实际采集时间: 0, 0.066, 0.133, 0.200, ... (实际15fps)
    - 视频以30fps播放 → 播放速度是实际的2倍！

解决方案：
""")

    print("\n1. 检查系统实际运行速度")
    print("   在数据采集时添加日志，记录真实的帧间隔")

    print("\n2. 修改时间戳生成方式")
    print("   使用真实的系统时间而不是 frame_index / fps")

    print("\n3. 优化系统性能")
    print("   确保系统能够稳定达到目标帧率（30fps）")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        parquet_file = sys.argv[1]
    else:
        parquet_file = "/home/dora/DoRobot-vr/dataset/leader-follower-x5/data/chunk-000/episode_000000.parquet"

    diagnose_framerate(parquet_file)
