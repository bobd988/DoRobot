"""
VR X5 Manipulator - Integrates VR hand controller with ARX-X5 arm
Receives data from DORA dataflow via ZeroMQ sockets
"""

import json
import time
import threading
import numpy as np
import cv2

# ========== 错误统计（减少日志刷屏） ==========
_joint_error_count = 0
_joint_error_last_print = 0
_joint_error_print_interval = 10  # 每10秒最多打印一次
import zmq
from pathlib import Path
from typing import Any

from operating_platform.robot.robots.utils import RobotDeviceNotConnectedError
from operating_platform.robot.robots.configs import VRX5RobotConfig
from operating_platform.robot.robots.camera import Camera


# ZeroMQ socket addresses (must match zeromq_sender.py)
IPC_ADDRESS_IMAGE = "ipc:///tmp/dora-zeromq-vr-x5-image"
IPC_ADDRESS_JOINT = "ipc:///tmp/dora-zeromq-vr-x5-joint"
IPC_ADDRESS_VR = "ipc:///tmp/dora-zeromq-vr-x5-vr"

# Global data storage
recv_images = {}
recv_joint = {}
recv_vr = {}
lock = threading.Lock()

# Thread control
running_recv_image_server = True
running_recv_joint_server = True
running_recv_vr_server = True

# Connection state
_image_connected = False
_joint_connected = False
_vr_connected = False

# ZeroMQ context and sockets
zmq_context = None
socket_image = None
socket_joint = None
socket_vr = None
_zmq_initialized = False


def _init_zmq():
    """Initialize ZeroMQ sockets (lazy initialization)"""
    global zmq_context, socket_image, socket_joint, socket_vr, _zmq_initialized

    if _zmq_initialized:
        return

    zmq_context = zmq.Context()

    # Use SUB sockets to match PUB sockets in zeromq_sender.py
    socket_image = zmq_context.socket(zmq.SUB)
    socket_image.connect(IPC_ADDRESS_IMAGE)
    socket_image.setsockopt(zmq.RCVTIMEO, 2000)
    socket_image.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages

    socket_joint = zmq_context.socket(zmq.SUB)
    socket_joint.connect(IPC_ADDRESS_JOINT)
    socket_joint.setsockopt(zmq.RCVTIMEO, 2000)
    socket_joint.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages

    socket_vr = zmq_context.socket(zmq.SUB)
    socket_vr.connect(IPC_ADDRESS_VR)
    socket_vr.setsockopt(zmq.RCVTIMEO, 2000)
    socket_vr.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages

    _zmq_initialized = True
    print("[VR X5] ZeroMQ sockets initialized")


def _cleanup_zmq():
    """Clean up ZeroMQ sockets and context"""
    global zmq_context, socket_image, socket_joint, socket_vr, _zmq_initialized
    global _image_connected, _joint_connected, _vr_connected

    if not _zmq_initialized:
        return

    try:
        if socket_image is not None:
            socket_image.close(linger=0)
            socket_image = None
        if socket_joint is not None:
            socket_joint.close(linger=0)
            socket_joint = None
        if socket_vr is not None:
            socket_vr.close(linger=0)
            socket_vr = None
        if zmq_context is not None:
            zmq_context.term()
            zmq_context = None

        _zmq_initialized = False
        _image_connected = False
        _joint_connected = False
        _vr_connected = False
        print("[VR X5] ZeroMQ sockets cleaned up")
    except Exception as e:
        print(f"[VR X5] Error cleaning up ZeroMQ: {e}")


def recv_image_server():
    """Receive image data from DORA via ZeroMQ"""
    global _image_connected
    while running_recv_image_server:
        if socket_image is None:
            time.sleep(0.1)
            continue
        try:
            message_parts = socket_image.recv_multipart()
            if len(message_parts) < 3:
                continue

            event_id = message_parts[0].decode('utf-8')
            buffer_bytes = message_parts[1]
            metadata = json.loads(message_parts[2].decode('utf-8'))

            if not _image_connected:
                _image_connected = True
                print("[VR X5] Camera data stream connected")

            if 'image' in event_id:
                # Decode image
                img_array = np.frombuffer(buffer_bytes, dtype=np.uint8)
                encoding = metadata["encoding"].lower()
                width = metadata["width"]
                height = metadata["height"]

                if encoding == "bgr8":
                    channels = 3
                    frame = img_array.reshape((height, width, channels)).copy()
                elif encoding == "rgb8":
                    channels = 3
                    frame = img_array.reshape((height, width, channels))
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                elif encoding in ["jpeg", "jpg", "jpe", "bmp", "webp", "png"]:
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                else:
                    print(f"[VR X5] Unsupported encoding: {encoding}")
                    continue

                with lock:
                    recv_images[event_id] = frame

        except zmq.Again:
            time.sleep(0.001)
        except Exception as e:
            if running_recv_image_server:
                print(f"[VR X5] Image receive error: {e}")
            time.sleep(0.1)


def recv_joint_server():
    """Receive joint data from ARX-X5 via ZeroMQ"""
    global _joint_connected
    while running_recv_joint_server:
        if socket_joint is None:
            time.sleep(0.1)
            continue
        try:
            message_parts = socket_joint.recv_multipart()
            if len(message_parts) < 2:
                continue

            event_id = message_parts[0].decode('utf-8')
            buffer_bytes = message_parts[1]

            if not _joint_connected:
                _joint_connected = True
                print("[VR X5] Joint data stream connected")

            # Parse joint data (JSON format from robot_driver_arx_x5.py)
            data = json.loads(buffer_bytes.decode('utf-8'))
            with lock:
                recv_joint[event_id] = data

        except zmq.Again:
            time.sleep(0.001)
        except Exception as e:
            if running_recv_joint_server:
                # ========== 减少错误日志刷屏 ==========
                global _joint_error_count, _joint_error_last_print
                _joint_error_count += 1
                now = time.time()
                # 每10秒最多打印一次错误统计
                if now - _joint_error_last_print >= _joint_error_print_interval:
                    print(f"[VR X5] Joint receive errors in last {_joint_error_print_interval}s: {_joint_error_count} (last error: {e})")
                    _joint_error_last_print = now
                    _joint_error_count = 0
            time.sleep(0.1)


def recv_vr_server():
    """Receive VR controller data via ZeroMQ"""
    global _vr_connected
    while running_recv_vr_server:
        if socket_vr is None:
            time.sleep(0.1)
            continue
        try:
            message_parts = socket_vr.recv_multipart()
            if len(message_parts) < 2:
                continue

            event_id = message_parts[0].decode('utf-8')
            buffer_bytes = message_parts[1]

            if not _vr_connected:
                _vr_connected = True
                print("[VR X5] VR data stream connected")

            # Parse VR data (JSON format from vr_ws_in.py)
            data = json.loads(buffer_bytes.decode('utf-8'))
            with lock:
                recv_vr[event_id] = data

        except zmq.Again:
            time.sleep(0.001)
        except Exception as e:
            if running_recv_vr_server:
                print(f"[VR X5] VR receive error: {e}")
            time.sleep(0.1)


class VRX5Manipulator:
    """
    VR X5 Manipulator - Receives data from DORA dataflow via ZeroMQ

    Data flow:
    - VR controller → vr_ws_in.py → zeromq_sender.py → ZeroMQ → VRX5Manipulator
    - ARX-X5 arm → robot_driver_arx_x5.py → zeromq_sender.py → ZeroMQ → VRX5Manipulator
    - Camera → camera_opencv → zeromq_sender.py → ZeroMQ → VRX5Manipulator
    """

    robot_type = "vr_x5"

    def __init__(self, config: VRX5RobotConfig):
        self.config = config
        self.is_connected_flag = False

        # Camera configuration
        self.cameras = {}
        self.camera_names = list(config.cameras.keys())

        # For compatibility with daemon.py logging
        # VR X5 doesn't have leader/follower arms concept
        self.follower_arms = {}
        self.leader_arms = {}
        self.logs = {}

        # Features for dataset
        self.features = self._build_features()

        # Receiver threads
        self.recv_threads = []

    def _build_features(self) -> dict:
        """Build feature dictionary for dataset"""
        features = {}

        # Camera features
        for name in self.camera_names:
            features[f"observation.images.{name}"] = {
                "dtype": "video",
                "shape": (480, 640, 3),
                "names": ["height", "width", "channels"],
            }

        # Joint state features (ARX-X5: 6 joints + gripper)
        features["observation.state"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "gripper"],
        }

        # VR controller features (position + rotation + buttons)
        features["observation.vr_state"] = {
            "dtype": "float32",
            "shape": (10,),
            "names": ["pos_x", "pos_y", "pos_z", "rot_x", "rot_y", "rot_z", "rot_w", "grip_active", "trigger", "timestamp"],
        }

        # Action features (commands sent to ARX-X5)
        features["action"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "gripper"],
        }

        return features

    @property
    def action_features(self) -> dict:
        """Return action features for dataset"""
        return {
            "action": self.features["action"]
        }

    @property
    def observation_features(self) -> dict:
        """Return observation features for dataset"""
        obs_features = {}
        for key, value in self.features.items():
            if key.startswith("observation."):
                obs_features[key] = value
        return obs_features

    @property
    def camera_features(self) -> dict:
        """Return camera features for dataset"""
        cam_features = {}
        for key, value in self.features.items():
            if "images" in key:
                cam_features[key] = value
        return cam_features

    @property
    def is_connected(self) -> bool:
        # VR connection is optional - only require image and joint data
        return self.is_connected_flag and _image_connected and _joint_connected

    def connect(self):
        """Connect to DORA dataflow via ZeroMQ"""
        if self.is_connected_flag:
            raise Exception("VR X5 Manipulator already connected")

        print("[VR X5] Connecting to DORA dataflow via ZeroMQ...")

        # Initialize ZeroMQ sockets
        _init_zmq()

        # Start receiver threads
        global running_recv_image_server, running_recv_joint_server, running_recv_vr_server
        running_recv_image_server = True
        running_recv_joint_server = True
        running_recv_vr_server = True

        thread_image = threading.Thread(target=recv_image_server, daemon=True)
        thread_joint = threading.Thread(target=recv_joint_server, daemon=True)
        thread_vr = threading.Thread(target=recv_vr_server, daemon=True)

        thread_image.start()
        thread_joint.start()
        thread_vr.start()

        self.recv_threads = [thread_image, thread_joint, thread_vr]

        # Wait for connections (VR is optional)
        print("[VR X5] Waiting for data streams...")
        timeout = 30
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Only require image and joint data, VR is optional
            if _image_connected and _joint_connected:
                break
            time.sleep(0.5)

        if not (_image_connected and _joint_connected):
            print(f"[VR X5] Warning: Required streams not connected after {timeout}s")
            print(f"  Image: {_image_connected}, Joint: {_joint_connected}")

        if not _vr_connected:
            print(f"[VR X5] Note: VR stream not connected (optional)")

        self.is_connected_flag = True
        print("[VR X5] Connected to DORA dataflow")

    def run_calibration(self):
        """VR X5 doesn't need calibration (handled by DORA nodes)"""
        print("[VR X5] Calibration not needed (handled by DORA nodes)")

    def teleop_step(self, record_data=False):
        """
        Perform one teleoperation step
        Returns (observation_dict, action_dict) if record_data=True
        """
        if not self.is_connected:
            raise RobotDeviceNotConnectedError("VR X5 Manipulator not connected")

        observation = self.capture_observation()

        if record_data:
            # Split observation and action into separate dicts
            action_dict = {}
            obs_dict = {}

            for key, value in observation.items():
                if key == "action":
                    # Action is the joint commands sent to the robot
                    action_dict["action"] = value
                else:
                    obs_dict[key] = value

            return obs_dict, action_dict

        return None

    def capture_observation(self):
        """Capture current observation from all sensors"""
        observation = {}

        with lock:
            # Capture images
            for camera_name in self.camera_names:
                event_id = f"image_{camera_name}"
                if event_id in recv_images:
                    observation[f"observation.images.{camera_name}"] = recv_images[event_id].copy()

            # Capture joint state (ARX-X5)
            if "joint" in recv_joint:
                joint_data = recv_joint["joint"]
                joint_positions = joint_data.get("joint_positions", [0] * 6)
                gripper = joint_data.get("gripper", 0)
                observation["observation.state"] = np.array(joint_positions + [gripper], dtype=np.float32)

            # Capture VR controller state
            if "vr_event" in recv_vr:
                vr_data = recv_vr["vr_event"]
                left_controller = vr_data.get("leftController", {})

                # Extract position (can be dict or list)
                pos_data = left_controller.get("position", [0, 0, 0])
                if isinstance(pos_data, dict):
                    position = [pos_data.get("x", 0), pos_data.get("y", 0), pos_data.get("z", 0)]
                else:
                    position = list(pos_data)

                # Extract rotation (can be dict or list)
                rot_data = left_controller.get("rotation", [0, 0, 0])
                if isinstance(rot_data, dict):
                    rotation = [rot_data.get("x", 0), rot_data.get("y", 0), rot_data.get("z", 0)]
                else:
                    rotation = list(rot_data)

                grip_active = float(left_controller.get("gripActive", False))
                trigger = left_controller.get("trigger", 0.0)
                timestamp = vr_data.get("timestamp", 0.0)

                vr_state = position + rotation + [grip_active, trigger, timestamp]
                observation["observation.vr_state"] = np.array(vr_state, dtype=np.float32)

            # Capture action (commands sent to ARX-X5)
            # This comes from arm_to_jointcmd_ik node
            if "action_joint" in recv_joint:
                action_data = recv_joint["action_joint"]
                if isinstance(action_data, list):
                    observation["action"] = np.array(action_data[:7], dtype=np.float32)

        return observation

    def send_action(self, action):
        """
        Send action to robot
        Note: For VR X5, actions are sent by DORA nodes, not by this class
        This method is here for compatibility with Robot protocol
        """
        print("[VR X5] Warning: send_action() not implemented (actions handled by DORA nodes)")

    def disconnect(self):
        """Disconnect from DORA dataflow"""
        if not self.is_connected_flag:
            return

        print("[VR X5] Disconnecting from DORA dataflow...")

        # Stop receiver threads
        global running_recv_image_server, running_recv_joint_server, running_recv_vr_server
        running_recv_image_server = False
        running_recv_joint_server = False
        running_recv_vr_server = False

        # Wait for threads to finish
        for thread in self.recv_threads:
            thread.join(timeout=2.0)

        # Clean up ZeroMQ
        _cleanup_zmq()

        self.is_connected_flag = False
        print("[VR X5] Disconnected")

    @property
    def use_videos(self) -> bool:
        return self.config.use_videos

    @property
    def microphones(self) -> dict:
        return {}  # No microphones for VR X5
