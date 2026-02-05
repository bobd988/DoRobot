#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR遥操ARX-X5数据录制节点（使用DoRobotDataset）
正确实现：保存PNG图像 → 编码成视频 → 删除PNG
"""

import os
import sys
import json
import logging
import signal
from pathlib import Path

import numpy as np
import pyarrow as pa

# 添加DoRobot路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node

from operating_platform.dataset.dorobot_dataset import DoRobotDataset

logging.basicConfig(level=logging.INFO)


class MockRobot:
    """简单的mock robot对象，用于DoRobotDataset.create()"""
    def __init__(self):
        self.microphones = {}  # 空字典，表示没有麦克风
        self.cameras = {}  # 空字典
        self.robot_type = "vr_x5"


class VRX5Recorder:
    def __init__(self):
        # 配置参数
        self.repo_id = os.environ.get("REPO_ID", "vr-x5-dataset")
        self.task = os.environ.get("SINGLE_TASK", "VR遥操ARX-X5机械臂")
        self.root = Path(os.environ.get("ROOT", "./dataset"))
        self.fps = int(os.environ.get("FPS", "30"))

        # 定义数据特征（手动定义，不依赖Robot）
        features = {
            "observation.images.camera_orbbec_top": {
                "dtype": "video",
                "shape": (480, 640, 3),
                "names": ["height", "width", "channels"],
                "info": {"video.fps": self.fps, "video.codec": "h264", "video.pix_fmt": "yuv420p"},
            },
            "observation.images.camera_orbbec_wrist": {
                "dtype": "video",
                "shape": (480, 640, 3),
                "names": ["height", "width", "channels"],
                "info": {"video.fps": self.fps, "video.codec": "h264", "video.pix_fmt": "yuv420p"},
            },
            "observation.state": {
                "dtype": "float32",
                "shape": (6,),
                "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"],
            },
            "action": {
                "dtype": "float32",
                "shape": (7,),
                "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "gripper"],
            },
        }

        # 创建mock robot对象
        mock_robot = MockRobot()

        # 清空旧数据集（每次启动都从干净状态开始）
        dataset_path = self.root / self.repo_id
        if dataset_path.exists():
            import shutil
            logging.info(f"[Recorder] Removing old dataset: {dataset_path}")
            shutil.rmtree(dataset_path)
            logging.info(f"[Recorder] Old dataset removed")

        # 创建新数据集（按照DoRobot项目的标准方式）
        logging.info(f"[Recorder] Creating new dataset: {dataset_path}")
        self.dataset = DoRobotDataset.create(
            repo_id=self.repo_id,
            fps=self.fps,
            root=self.root,
            robot=mock_robot,  # 传入mock robot
            robot_type="vr_x5",
            features=features,
            use_videos=True,  # 使用视频编码
            image_writer_processes=0,  # 不使用子进程
            image_writer_threads=4,  # 4个写入线程（与DoRobot项目一致）
        )
        # 注意：create()会自动调用start_image_writer()，不需要手动调用

        # 录制状态
        self.recording = False
        self.last_joint = None
        self.last_action = None
        self.last_vr = None
        self.last_image_top = None
        self.last_image_wrist = None

        # 真实时间戳记录（用于修复视频播放速度问题）
        # 记录episode开始的真实时间，用于计算每帧的真实时间戳
        # 这样视频播放速度就会与实际操作速度一致
        self.episode_start_time = None

        logging.info(f"[Recorder] Initialized")
        logging.info(f"  repo_id: {self.repo_id}")
        logging.info(f"  root: {self.root}")
        logging.info(f"  task: {self.task}")
        logging.info(f"  fps: {self.fps}")
        logging.info(f"  total_episodes: {self.dataset.meta.total_episodes}")

    def start_episode(self):
        """开始新episode"""
        if self.recording:
            logging.warning("[Recorder] Already recording!")
            return

        self.recording = True

        # 记录episode开始的真实时间（用于计算真实时间戳）
        # 这样可以确保视频播放速度与实际操作速度一致
        import time
        self.episode_start_time = time.time()

        # DoRobotDataset会自动创建episode_buffer
        if self.dataset.episode_buffer is None:
            self.dataset.episode_buffer = self.dataset.create_episode_buffer()

        episode_idx = self.dataset.episode_buffer.get("episode_index", "?")
        logging.info(f"[Recorder] Started episode {episode_idx}")

    def add_frame(self):
        """添加一帧数据到episode_buffer"""
        if not self.recording:
            return

        # 构建帧数据
        frame = {}

        # 添加顶部相机图像（RGB格式，HWC）
        if self.last_image_top is not None:
            frame["observation.images.camera_orbbec_top"] = self.last_image_top

        # 添加腕部相机图像（RGB格式，HWC）
        if self.last_image_wrist is not None:
            frame["observation.images.camera_orbbec_wrist"] = self.last_image_wrist

        # 添加关节状态
        if self.last_joint is not None:
            frame["observation.state"] = np.array(self.last_joint[:6], dtype=np.float32)

        # 添加动作
        if self.last_action is not None:
            frame["action"] = np.array(self.last_action[:7], dtype=np.float32)

        # 添加真实时间戳（修复视频播放速度问题）
        # 原来的实现使用 frame_index / fps 计算时间戳，假设系统完美运行在30fps
        # 但实际采集可能慢于30fps，导致视频播放速度快于实际操作速度
        # 现在使用真实的系统时间，确保视频播放速度与实际操作速度一致
        if self.episode_start_time is not None:
            import time
            frame['timestamp'] = time.time() - self.episode_start_time

        # 使用DoRobotDataset的add_frame方法
        # 它会自动保存图像为PNG到临时目录
        try:
            self.dataset.add_frame(frame, self.task)
        except Exception as e:
            logging.error(f"[Recorder] Failed to add frame: {e}")

    def save_episode(self):
        """保存episode（PNG → MP4 → 删除PNG）"""
        if not self.recording:
            logging.warning("[Recorder] Not recording!")
            return

        self.recording = False

        try:
            episode_idx = self.dataset.episode_buffer.get("episode_index", "?")
            frame_count = self.dataset.episode_buffer.get("size", 0)

            logging.info(f"[Recorder] Saving episode {episode_idx} ({frame_count} frames)...")

            # 使用DoRobotDataset的save_episode方法
            # 它会：
            # 1. 等待PNG图像写入完成
            # 2. 使用ffmpeg编码成MP4
            # 3. 删除临时PNG图像
            saved_idx = self.dataset.save_episode(skip_encoding=False)

            logging.info(f"[Recorder] Episode {saved_idx} saved successfully!")

        except Exception as e:
            logging.error(f"[Recorder] Failed to save episode: {e}")
            import traceback
            traceback.print_exc()


def extract_bytes(value):
    """从Dora值中提取字节数据"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None

        # 兼容：如果是"整数数组"（uint8/int8/int64...），按字节拼回 bytes
        try:
            if pa.types.is_integer(value.type):
                ints = value.to_pylist()
                ints = [x for x in ints if x is not None]
                return bytes((int(x) & 0xFF) for x in ints)
        except Exception:
            pass

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


def extract_image(value):
    """从Dora值中提取图像（RGB格式，HWC）"""
    if value is None:
        return None

    if isinstance(value, pa.Array):
        try:
            # camera_opencv发送的是展平的数组
            img_flat = value.to_numpy()
            # 假设是640x480 BGR图像
            if len(img_flat) == 640 * 480 * 3:
                img_bgr = img_flat.reshape((480, 640, 3))
                # 转换为RGB��DoRobotDataset期望RGB格式）
                import cv2
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                return img_rgb
        except Exception as e:
            logging.error(f"[Recorder] Failed to extract image: {e}")

    return None


def main():
    recorder = VRX5Recorder()

    # 信号处理
    def signal_handler(sig, frame):
        logging.info("[Recorder] Received signal, saving...")
        if recorder.recording:
            recorder.save_episode()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # DORA节点
    node = Node()

    logging.info("[Recorder] Ready. Press grip to start recording.")

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

            # 接收顶部相机图像
            if event_id == "image_top":
                recorder.last_image_top = extract_image(value)
                # 只在接收到顶部相机图像时添加帧（图像是30fps的主时钟）
                if recorder.recording:
                    recorder.add_frame()

            # 接收腕部相机图像
            elif event_id == "image_wrist":
                recorder.last_image_wrist = extract_image(value)

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
                        # 调试：打印VR数据类型和内容
                        if not isinstance(vr, dict):
                            logging.error(f"[Recorder] VR data is not dict, type={type(vr)}, value={vr}")
                            continue

                        # 注意：JSON中的键是 leftController 而不是 left
                        left_controller = vr.get("leftController")
                        if left_controller is None:
                            # 可能没有leftController键，跳过
                            continue

                        if not isinstance(left_controller, dict):
                            logging.error(f"[Recorder] leftController is not dict, type={type(left_controller)}, value={left_controller}")
                            continue

                        recorder.last_vr = left_controller

                        # 检测握把状态变化（注意：键是 gripActive 而不是 grip）
                        grip = bool(left_controller.get("gripActive", False))
                        if grip and not recorder.recording:
                            # 握把按下：开始录制
                            recorder.start_episode()
                        elif not grip and recorder.recording:
                            # 握把松开：保存episode
                            recorder.save_episode()
                    except json.JSONDecodeError as e:
                        logging.error(f"[Recorder] JSON decode error: {e}")
                    except Exception as e:
                        logging.error(f"[Recorder] VR event error: {e}, type={type(e)}")

    # 清理
    if recorder.recording:
        recorder.save_episode()

    logging.info("[Recorder] Stopped")


if __name__ == "__main__":
    main()
