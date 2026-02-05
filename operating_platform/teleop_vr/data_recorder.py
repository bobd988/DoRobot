#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR遥操ARX-X5数据保存节点
直接保存为DoRobot格式（Parquet + MP4 + JSON）
"""

import os
import sys
import json
import time
import signal
from pathlib import Path
from datetime import datetime

import numpy as np
import pyarrow as pa
import pandas as pd
import cv2

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


class VRX5DataRecorder:
    def __init__(self):
        # 配置参数
        self.repo_id = os.environ.get("REPO_ID", "vr-x5-dataset")
        self.task = os.environ.get("SINGLE_TASK", "VR遥操ARX-X5")
        self.root = Path(os.environ.get("ROOT", "./dataset"))
        self.fps = int(os.environ.get("FPS", "30"))

        # 数据集路径
        self.dataset_path = self.root / self.repo_id
        self.data_path = self.dataset_path / "data" / "chunk-000"
        self.video_path = self.dataset_path / "videos" / "chunk-000" / "camera_orbbec"
        self.meta_path = self.dataset_path / "meta"

        # 创建目录
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.video_path.mkdir(parents=True, exist_ok=True)
        self.meta_path.mkdir(parents=True, exist_ok=True)

        # 当前episode
        self.episode_index = 0
        self.frame_index = 0
        self.recording = False
        self.episode_data = []
        self.video_writer = None

        # 最后接收的数据
        self.last_joint = None
        self.last_action = None
        self.last_vr = None

        print(f"[data_recorder] Initialized")
        print(f"  repo_id: {self.repo_id}")
        print(f"  task: {self.task}")
        print(f"  dataset_path: {self.dataset_path}")

    def start_episode(self):
        """开始新episode"""
        self.recording = True
        self.frame_index = 0
        self.episode_data = []

        # 创建视频写入器
        video_file = self.video_path / f"episode_{self.episode_index:06d}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            str(video_file),
            fourcc,
            self.fps,
            (640, 480)
        )

        print(f"[data_recorder] Started episode {self.episode_index}")

    def add_frame(self, image, joint, action, vr):
        """添加一帧数据"""
        if not self.recording:
            return

        # 保存图像帧
        if image is not None and self.video_writer is not None:
            self.video_writer.write(image)

        # 保存结构化数据
        frame_data = {
            'timestamp': time.time(),
            'frame_index': self.frame_index,
            'episode_index': self.episode_index,
            'task_index': 0,
        }

        # 添加关节数据
        if joint is not None:
            frame_data['observation.state'] = joint[:6]  # 6个关节

        # 添加动作数据
        if action is not None:
            frame_data['action'] = action[:7]  # 6关节+夹爪

        # 添加VR数据
        if vr is not None:
            frame_data['observation.vr_pos'] = vr.get('pos', [0, 0, 0])
            frame_data['observation.vr_quat'] = vr.get('quat', [0, 0, 0, 1])
            frame_data['observation.vr_grip'] = vr.get('grip', False)
            frame_data['observation.vr_trigger'] = vr.get('trigger', 0.0)

        # 添加图像路径
        frame_data['observation.images.camera_orbbec'] = f"videos/chunk-000/camera_orbbec/episode_{self.episode_index:06d}.mp4"

        self.episode_data.append(frame_data)
        self.frame_index += 1

    def save_episode(self):
        """保存episode"""
        if not self.recording:
            return

        self.recording = False

        # 关闭视频写入器
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        # 保存Parquet文件
        if len(self.episode_data) > 0:
            df = pd.DataFrame(self.episode_data)
            parquet_file = self.data_path / f"episode_{self.episode_index:06d}.parquet"
            df.to_parquet(parquet_file, index=False)

            print(f"[data_recorder] Saved episode {self.episode_index} ({len(self.episode_data)} frames)")

            # 更新元数据
            self.update_metadata()

            self.episode_index += 1
            self.episode_data = []

    def update_metadata(self):
        """更新元数据文件"""
        # info.json
        info = {
            'codebase_version': 'v1.0',
            'robot_type': 'vr_x5',
            'fps': self.fps,
            'total_episodes': self.episode_index + 1,
            'total_frames': sum(len(pd.read_parquet(f)) for f in self.data_path.glob('*.parquet')),
            'total_tasks': 1,
            'features': {
                'observation.state': {'dtype': 'float32', 'shape': [6]},
                'action': {'dtype': 'float32', 'shape': [7]},
                'observation.vr_pos': {'dtype': 'float32', 'shape': [3]},
                'observation.vr_quat': {'dtype': 'float32', 'shape': [4]},
            }
        }

        with open(self.meta_path / 'info.json', 'w') as f:
            json.dump(info, f, indent=2)

        # episodes.jsonl
        episode_meta = {
            'episode_index': self.episode_index,
            'tasks': [self.task],
            'length': len(self.episode_data),
            'timestamp': datetime.now().isoformat()
        }

        with open(self.meta_path / 'episodes.jsonl', 'a') as f:
            f.write(json.dumps(episode_meta) + '\n')


def extract_bytes(value):
    """从Dora值中提取字节数据"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
        item = value[0].as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return str(item).encode("utf-8")
    return None


def extract_float_list(value):
    """从Dora值中提取浮点数列表"""
    if value is None:
        return None
    if isinstance(value, pa.Array):
        try:
            xs = value.to_pylist()
            xs = [x for x in xs if x is not None]
            if not xs:
                return None
            return [float(x) for x in xs]
        except Exception:
            pass
    return None


def main():
    recorder = VRX5DataRecorder()

    # 信号处理
    def signal_handler(sig, frame):
        print("[data_recorder] Received signal, saving...")
        if recorder.recording:
            recorder.save_episode()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # DORA节点
    node = Node()

    print("[data_recorder] Ready. Press 'n' to save episode.")

    # 主循环
    for event in node:
        event_type = event.get("type")

        if event_type == "STOP":
            if recorder.recording:
                recorder.save_episode()
            break

        if event_type == "INPUT":
            event_id = event.get("id")
            value = event.get("value")

            # 接收图像
            if event_id == "image":
                # 将PyArrow数组转换为numpy数组
                if isinstance(value, pa.Array):
                    img_bytes = value.to_pylist()
                    img_array = np.array(img_bytes, dtype=np.uint8)
                    # 假设是640x480 BGR图像
                    if len(img_array) == 640 * 480 * 3:
                        image = img_array.reshape((480, 640, 3))

                        # 如果正在录制，添加帧
                        if recorder.recording:
                            recorder.add_frame(
                                image,
                                recorder.last_joint,
                                recorder.last_action,
                                recorder.last_vr
                            )

            # 接收关节数据
            elif event_id == "joint":
                raw = extract_bytes(value)
                if raw:
                    try:
                        data = json.loads(raw.decode("utf-8"))
                        recorder.last_joint = data.get("joint_positions")
                    except Exception:
                        pass

            # 接收动作命令
            elif event_id == "action_joint":
                recorder.last_action = extract_float_list(value)

            # 接收VR数据
            elif event_id == "vr_event":
                raw = extract_bytes(value)
                if raw:
                    try:
                        vr = json.loads(raw.decode("utf-8"))
                        if isinstance(vr.get("left"), dict):
                            recorder.last_vr = vr["left"]

                            # 检测握把状态变化
                            grip = bool(recorder.last_vr.get("grip", False))
                            if grip and not recorder.recording:
                                # 握把按下：开始录制
                                recorder.start_episode()
                            elif not grip and recorder.recording:
                                # 握把松开：保存episode
                                recorder.save_episode()
                    except Exception:
                        pass

            # 接收控制命令
            elif event_id == "control":
                raw = extract_bytes(value)
                if raw:
                    cmd = raw.decode("utf-8").strip()
                    if cmd == "save" or cmd == "n":
                        if recorder.recording:
                            recorder.save_episode()
                            recorder.start_episode()  # 开始新episode
                    elif cmd == "exit" or cmd == "e":
                        if recorder.recording:
                            recorder.save_episode()
                        sys.exit(0)

    # 清理
    if recorder.recording:
        recorder.save_episode()


if __name__ == "__main__":
    main()
