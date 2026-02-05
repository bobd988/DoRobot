#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试data_recorder是否能正常保存数据
"""

import os
import sys
import json
import time
import numpy as np

# 设置环境变量
os.environ["REPO_ID"] = "test-dataset"
os.environ["SINGLE_TASK"] = "测试录制"
os.environ["ROOT"] = "./dataset"
os.environ["FPS"] = "30"

# 导入data_recorder
sys.path.insert(0, os.path.dirname(__file__))
from data_recorder import VRX5DataRecorder

def test_recording():
    print("=" * 60)
    print("测试data_recorder录制功能")
    print("=" * 60)

    recorder = VRX5DataRecorder()

    # 模拟录制一个episode
    print("\n1. 开始episode...")
    recorder.start_episode()

    # 模拟添加10帧数据
    print("2. 添加10帧测试数据...")
    for i in range(10):
        # 模拟图像（640x480 BGR）
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # 模拟关节数据
        joint = [0.1 * i] * 6

        # 模拟动作数据
        action = [0.2 * i] * 7

        # 模拟VR数据
        vr = {
            'pos': [0.1, 0.2, 0.3],
            'quat': [0, 0, 0, 1],
            'grip': True,
            'trigger': 0.5
        }

        recorder.add_frame(image, joint, action, vr)
        time.sleep(0.033)  # 30fps

    print(f"   已添加 {recorder.frame_index} 帧")

    # 保存episode
    print("3. 保存episode...")
    recorder.save_episode()

    # 检查保存的文件
    print("\n4. 检查保存的文件:")
    dataset_path = recorder.dataset_path

    parquet_file = dataset_path / "data" / "chunk-000" / "episode_000000.parquet"
    video_file = dataset_path / "videos" / "chunk-000" / "camera_orbbec" / "episode_000000.mp4"
    info_file = dataset_path / "meta" / "info.json"
    episodes_file = dataset_path / "meta" / "episodes.jsonl"

    print(f"   Parquet: {parquet_file.exists()} - {parquet_file}")
    print(f"   Video:   {video_file.exists()} - {video_file}")
    print(f"   Info:    {info_file.exists()} - {info_file}")
    print(f"   Episodes:{episodes_file.exists()} - {episodes_file}")

    if parquet_file.exists():
        import pandas as pd
        df = pd.read_parquet(parquet_file)
        print(f"\n   Parquet内容: {len(df)} 行")
        print(f"   列: {list(df.columns)}")

    if video_file.exists():
        import cv2
        cap = cv2.VideoCapture(str(video_file))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        print(f"\n   视频帧数: {frame_count}")

    print("\n" + "=" * 60)
    if parquet_file.exists() and video_file.exists():
        print("✅ 测试成功！data_recorder工作正常")
    else:
        print("❌ 测试失败！data_recorder有问���")
    print("=" * 60)

if __name__ == "__main__":
    test_recording()
