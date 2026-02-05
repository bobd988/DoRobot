#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证真实时间戳修复效果

使用方法：
1. 重新采集一段数据
2. 运行此脚本检查时间戳是否使用了真实时间
3. 播放视频，检查速度是否与实际操作一致
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
import sys

def verify_timestamps(parquet_file: str):
    """验证时间戳是否使用了真实时间"""
    
    if not Path(parquet_file).exists():
        print(f"❌ 文件不存在: {parquet_file}")
        return False
    
    # 读取数据
    df = pq.read_table(parquet_file).to_pandas()
    timestamps = df['timestamp'].values
    
    print("=" * 70)
    print("时间戳验证报告")
    print("=" * 70)
    print(f"\n数据文件: {parquet_file}")
    print(f"总帧数: {len(timestamps)}")
    print(f"时间范围: {timestamps[0]:.3f}s - {timestamps[-1]:.3f}s")
    print(f"总时长: {timestamps[-1] - timestamps[0]:.3f}s")
    
    # 计算帧间隔
    intervals = []
    for i in range(1, min(50, len(timestamps))):
        interval = timestamps[i] - timestamps[i-1]
        intervals.append(interval)
    
    import numpy as np
    intervals = np.array(intervals)
    
    avg_interval = np.mean(intervals)
    std_interval = np.std(intervals)
    min_interval = np.min(intervals)
    max_interval = np.max(intervals)
    
    print(f"\n帧间隔统计（前50帧）:")
    print(f"  平均间隔: {avg_interval:.4f}s ({1/avg_interval:.2f} fps)")
    print(f"  标准差: {std_interval:.4f}s")
    print(f"  最小间隔: {min_interval:.4f}s")
    print(f"  最大间隔: {max_interval:.4f}s")
    
    print(f"\n前10个帧间隔:")
    for i in range(min(10, len(intervals))):
        print(f"  frame_{i}->{i+1}: {intervals[i]:.4f}s ({1/intervals[i]:.1f} fps)")
    
    print("\n" + "=" * 70)
    print("验证结果:")
    print("=" * 70)
    
    # 判断是否使用了真实时间戳
    # 如果标准差很小（< 0.001），说明是理想的等间隔，使用了计算的时间戳
    # 如果标准差较大（> 0.001），说明有波动，使用了真实时间戳
    
    if std_interval < 0.001:
        print("❌ 时间戳是理想的等间隔")
        print("   说明：仍在使用 frame_index / fps 计算")
        print("   问题：如果实际采集慢于30fps，视频会比实际快")
        print("\n建议：")
        print("   1. 检查 data_recorder_v2.py 是否正确添加了真实时间戳")
        print("   2. 检查 dorobot_dataset.py 是否正确使用了真实时间戳")
        print("   3. 重新启动系统并采集数据")
        return False
    else:
        print("✓ 时间戳有波动，使用了真实时间")
        print(f"   标准差: {std_interval:.4f}s")
        print(f"   实际平均帧率: {1/avg_interval:.2f} fps")
        print("   效果：视频播放速度将与实际操作速度一致")
        
        # 检查实际帧率是否接近30fps
        actual_fps = 1 / avg_interval
        if abs(actual_fps - 30) > 5:
            print(f"\n⚠ 警告：实际帧率 ({actual_fps:.1f} fps) 偏离目标30fps较多")
            print("   可能原因：系统负载高，相机采集延迟")
            print("   建议：优化系统性能或降低目标帧率")
        
        return True
    
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parquet_file = sys.argv[1]
    else:
        # 默认检查最新的数据集
        parquet_file = "/home/dora/DoRobot-vr/dataset/leader-follower-x5/data/chunk-000/episode_000000.parquet"
    
    verify_timestamps(parquet_file)
