#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据格式转换脚本
将当前的Parquet格式转换为交付标准的JSONL格式

输入: leader-follower-x5/ (Parquet + MP4)
输出: leader-follower-x5-converted/ (JSONL + 重组的目录结构)
"""

import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from typing import Dict, List, Any

# 导入FK计算器
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from fk_calculator import ForwardKinematicsCalculator
    FK_AVAILABLE = True
except Exception as e:
    print(f"⚠ 无法导入FK计算器: {e}")
    print("  将使用占位符代替end_effector_pose")
    FK_AVAILABLE = False


class DataConverter:
    def __init__(self, input_dir: str, output_dir: str, task_name: str = "leader_follower_x5"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.task_name = task_name

        # 初始化FK计算器
        if FK_AVAILABLE:
            try:
                self.fk = ForwardKinematicsCalculator()
                self.use_real_fk = True
                print("✓ FK计算器初始化成功，将使用真实的end_effector_pose")
            except Exception as e:
                print(f"⚠ FK计算器初始化失败: {e}")
                print("  将使用占位符")
                self.use_real_fk = False
        else:
            self.use_real_fk = False

    def calculate_actual_fps(self) -> float:
        """
        从时间戳计算实际fps
        读取第一个可用的episode，从其时间戳计算实际帧率
        """
        # 查找第一个parquet文件
        parquet_files = list(self.input_dir.glob("data/chunk-*/episode_*.parquet"))

        if not parquet_files:
            print("⚠ 未找到parquet文件，使用默认fps=30")
            return 30.0

        # 读取第一个episode
        first_parquet = parquet_files[0]
        table = pq.read_table(str(first_parquet))
        df = table.to_pandas()

        # 从时间戳计算实际fps
        if len(df) > 1:
            timestamps = df['timestamp'].values
            total_duration = timestamps[-1] - timestamps[0]
            num_intervals = len(timestamps) - 1

            if total_duration > 0:
                actual_fps = num_intervals / total_duration
                print(f"✓ 从时间戳计算实际fps: {actual_fps:.2f}")
                return actual_fps

        # 如果计算失败，返回默认值
        print("⚠ 无法从时间戳计算fps，使用默认fps=30")
        return 30.0

    def convert_dataset(self):
        """转换整个数据集"""
        print("=" * 70)
        print("数据格式转换工具")
        print("=" * 70)

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 查找所有parquet文件
        parquet_files = list(self.input_dir.glob("data/chunk-*/episode_*.parquet"))

        if not parquet_files:
            print("❌ 未找到parquet文件")
            return

        print(f"\n找到 {len(parquet_files)} 个episode")

        # 转换每个episode
        for parquet_file in parquet_files:
            episode_name = parquet_file.stem  # episode_000000
            print(f"\n处理 {episode_name}...")
            self.convert_episode(parquet_file, episode_name)

        # 生成全局元数据
        self.generate_task_desc()
        self.generate_task_info()

        print("\n" + "=" * 70)
        print("✓ 转换完成!")
        print(f"输出目录: {self.output_dir}")
        print("=" * 70)

    def convert_episode(self, parquet_file: Path, episode_name: str):
        """转换单个episode"""
        # 读取parquet数据
        table = pq.read_table(str(parquet_file))
        df = table.to_pandas()

        # 创建episode目录
        episode_dir = self.output_dir / "data" / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        meta_dir = episode_dir / "meta"
        states_dir = episode_dir / "states"
        videos_dir = episode_dir / "videos"

        meta_dir.mkdir(exist_ok=True)
        states_dir.mkdir(exist_ok=True)
        videos_dir.mkdir(exist_ok=True)

        # 1. 生成states.jsonl
        print(f"  生成 states.jsonl...")
        self.generate_states_jsonl(df, states_dir / "states.jsonl")

        # 2. 生成episode_meta.json
        print(f"  生成 episode_meta.json...")
        self.generate_episode_meta(df, episode_name, meta_dir / "episode_meta.json")

        # 3. 复制视频文件
        print(f"  复制视频文件...")
        self.copy_videos(episode_name, videos_dir)

        print(f"  ✓ {episode_name} 转换完成")

    def generate_states_jsonl(self, df: pd.DataFrame, output_file: Path):
        """生成states.jsonl文件"""
        with open(output_file, 'w') as f:
            for i in range(len(df)):
                # 提取数据
                action = df['action'].iloc[i]
                obs_state = df['observation.state'].iloc[i]
                timestamp = df['timestamp'].iloc[i]

                # 构建state字典 (确保所有值都是Python原生类型)
                state = {
                    # 关节位置 (从observation.state提取前6个)
                    "joint_positions": [float(x) for x in obs_state[:6]],

                    # 关节速度 (从相邻帧计算)
                    "joint_velocities": [float(x) for x in self.calculate_velocities(df, i, 'observation.state', 6)],

                    # 末端执行器位姿 (通过正运动学计算)
                    "end_effector_pose": [float(x) for x in self.get_end_effector_pose(obs_state[:6])],

                    # 夹爪宽度 (从observation.state第7个值转换)
                    "gripper_width": float(obs_state[6]),

                    # 夹爪速度 (从相邻帧计算)
                    "gripper_velocity": float(self.calculate_gripper_velocity(df, i)),

                    # 时间戳
                    "timestamp": float(timestamp)
                }

                # 写入JSONL
                f.write(json.dumps(state) + '\n')

    def calculate_velocities(self, df: pd.DataFrame, index: int, column: str, num_joints: int) -> List[float]:
        """计算关节速度"""
        if index == 0:
            # 第一帧，速度为0
            return [0.0] * num_joints

        # 当前位置和上一帧位置
        current_pos = df[column].iloc[index][:num_joints]
        prev_pos = df[column].iloc[index-1][:num_joints]

        # 时间差
        dt = df['timestamp'].iloc[index] - df['timestamp'].iloc[index-1]

        if dt <= 0:
            return [0.0] * num_joints

        # 速度 = (位置差) / 时间差
        velocities = [(current_pos[i] - prev_pos[i]) / dt for i in range(num_joints)]

        return velocities

    def calculate_gripper_velocity(self, df: pd.DataFrame, index: int) -> float:
        """计算夹爪速度"""
        if index == 0:
            return 0.0

        # 当前和上一帧的夹爪值
        current_gripper = df['observation.state'].iloc[index][6]
        prev_gripper = df['observation.state'].iloc[index-1][6]

        # 时间差
        dt = df['timestamp'].iloc[index] - df['timestamp'].iloc[index-1]

        if dt <= 0:
            return 0.0

        return float((current_gripper - prev_gripper) / dt)

    def get_end_effector_pose(self, joint_positions) -> List[float]:
        """获取末端执行器位姿"""
        if self.use_real_fk:
            try:
                # 使用FK计算器计算真实位姿
                pose = self.fk.calculate(joint_positions.tolist())
                return pose
            except Exception as e:
                print(f"    ⚠ FK计算失败: {e}, 使用占位符")
                return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        else:
            # 使用占位符
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def generate_episode_meta(self, df: pd.DataFrame, episode_name: str, output_file: Path):
        """生成episode_meta.json"""
        # 提取episode索引
        episode_index = int(episode_name.split('_')[-1])

        # 获取时间信息
        start_time = float(df['timestamp'].iloc[0])
        end_time = float(df['timestamp'].iloc[-1])
        frames = len(df)

        meta = {
            "episode_index": episode_index,
            "start_time": start_time,
            "end_time": end_time,
            "frames": frames
        }

        with open(output_file, 'w') as f:
            json.dump(meta, f, indent=2)

    def copy_videos(self, episode_name: str, videos_dir: Path):
        """复制并重命名视频文件"""
        # 查找视频文件
        video_base = self.input_dir / "videos" / "chunk-000"

        # 映射关系: 当前名称 -> 目标名称
        video_mapping = {
            "observation.images.top": "global_realsense_rgb.mp4",
            "observation.images.wrist": "arm_realsense_rgb.mp4",
            "observation.images.right_realsense": "right_realsense_rgb.mp4",
        }

        for src_name, dst_name in video_mapping.items():
            src_file = video_base / src_name / f"{episode_name}.mp4"
            dst_file = videos_dir / dst_name

            if src_file.exists():
                shutil.copy2(src_file, dst_file)
                print(f"    ✓ {dst_name}")
            else:
                print(f"    ⚠ 未找到 {src_file}")

    def generate_task_desc(self):
        """生成task_desc.json"""
        # 从时间戳计算实际fps（确保与视频编码fps一致）
        actual_fps = self.calculate_actual_fps()

        task_desc = {
            "robot_id": "arx5_leader_follower",
            "task_desc": {
                "task_name": self.task_name,
                "prompt": "Leader-follower teleoperation with Feetech leader arm and ARX-X5 follower arm",
                "scoring": "Data quality based on smoothness and accuracy of teleoperation",
                "task_tag": [
                    "teleoperation",
                    "leader-follower",
                    "dual-arm",
                    "ARX5"
                ]
            },
            "video_info": {
                "fps": int(round(actual_fps)),  # 使用从时间戳计算的实际fps
                "ext": "mp4",
                "encoding": {
                    "vcodec": "libx264",
                    "pix_fmt": "yuv420p"
                }
            }
        }

        output_file = self.output_dir / "task_desc.json"
        with open(output_file, 'w') as f:
            json.dump(task_desc, f, indent=2)

        print(f"\n✓ 生成 task_desc.json (fps={int(round(actual_fps))})")

    def generate_task_info(self):
        """生成task_info.json"""
        # 统计所有episodes
        data_dir = self.output_dir / "data"
        episodes = sorted(data_dir.glob("episode_*"))

        task_info = {
            "task_name": self.task_name,
            "total_episodes": len(episodes),
            "robot_type": "ARX5",
            "control_mode": "leader-follower",
            "data_format_version": "1.0"
        }

        meta_dir = self.output_dir / "meta"
        meta_dir.mkdir(exist_ok=True)

        output_file = meta_dir / "task_info.json"
        with open(output_file, 'w') as f:
            json.dump(task_info, f, indent=2)

        print(f"✓ 生成 task_info.json")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='转换数据格式为交付标准')
    parser.add_argument('--input', '-i',
                       default='/home/dora/DoRobot-vr/dataset/leader-follower-x5',
                       help='输入目录 (默认: /home/dora/DoRobot-vr/dataset/leader-follower-x5)')
    parser.add_argument('--output', '-o',
                       default='/home/dora/DoRobot-vr/dataset/leader-follower-x5-converted',
                       help='输出目录 (默认: /home/dora/DoRobot-vr/dataset/leader-follower-x5-converted)')
    parser.add_argument('--task-name', '-t',
                       default='leader_follower_x5',
                       help='任务名称 (默认: leader_follower_x5)')

    args = parser.parse_args()

    # 创建转换器并执行转换
    converter = DataConverter(args.input, args.output, args.task_name)
    converter.convert_dataset()


if __name__ == "__main__":
    main()
