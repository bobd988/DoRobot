"""
Leader X5 Manipulator - Leader-Follower teleoperation
Receives data from DORA dataflow via ZeroMQ sockets
"""

import json
import time
import threading
import numpy as np
import cv2
import zmq
from pathlib import Path
from typing import Any

from operating_platform.robot.robots.utils import RobotDeviceNotConnectedError
from operating_platform.robot.robots.configs import LeaderX5RobotConfig

# ZeroMQ socket addresses (must match dora_zeromq.py)
IPC_ADDRESS_IMAGE = "ipc:///tmp/dora-zeromq-leader-follower-image"
IPC_ADDRESS_JOINT = "ipc:///tmp/dora-zeromq-leader-follower-joint"

# Global data storage
recv_images = {}
recv_joint = {}
lock = threading.Lock()

# Thread control
running_recv_image_server = True
running_recv_joint_server = True

# Connection state
_image_connected = False
_joint_connected = False

# ZeroMQ context and sockets
zmq_context = None
socket_image = None
socket_joint = None
_zmq_initialized = False


def _init_zmq():
    """Initialize ZeroMQ sockets (lazy initialization)"""
    global zmq_context, socket_image, socket_joint, _zmq_initialized

    if _zmq_initialized:
        return

    zmq_context = zmq.Context()

    # Use SUB sockets to match PUB sockets in dora_zeromq.py
    socket_image = zmq_context.socket(zmq.SUB)
    socket_image.connect(IPC_ADDRESS_IMAGE)
    socket_image.setsockopt(zmq.RCVTIMEO, 2000)
    socket_image.setsockopt_string(zmq.SUBSCRIBE, "")

    socket_joint = zmq_context.socket(zmq.SUB)
    socket_joint.connect(IPC_ADDRESS_JOINT)
    socket_joint.setsockopt(zmq.RCVTIMEO, 2000)
    socket_joint.setsockopt_string(zmq.SUBSCRIBE, "")

    _zmq_initialized = True
    print("[Leader X5] ZeroMQ sockets initialized")


def _cleanup_zmq():
    """Clean up ZeroMQ sockets and context"""
    global zmq_context, socket_image, socket_joint, _zmq_initialized
    global _image_connected, _joint_connected

    if not _zmq_initialized:
        return

    try:
        if socket_image is not None:
            socket_image.close(linger=0)
            socket_image = None
        if socket_joint is not None:
            socket_joint.close(linger=0)
            socket_joint = None
        if zmq_context is not None:
            zmq_context.term()
            zmq_context = None

        _zmq_initialized = False
        _image_connected = False
        _joint_connected = False
        print("[Leader X5] ZeroMQ sockets cleaned up")
    except Exception as e:
        print(f"[Leader X5] Error cleaning up ZeroMQ: {e}")


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
                print("[Leader X5] Camera data stream connected")

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
                    print(f"[Leader X5] Unsupported encoding: {encoding}")
                    continue

                with lock:
                    recv_images[event_id] = frame

        except zmq.Again:
            time.sleep(0.001)
        except Exception as e:
            if running_recv_image_server:
                print(f"[Leader X5] Image receive error: {e}")
            time.sleep(0.1)


def recv_joint_server():
    """Receive joint data from leader and follower arms via ZeroMQ"""
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
                print("[Leader X5] Joint data stream connected")

            # Parse joint data based on source:
            # - Leader arm: raw numpy float32 array
            # - Follower arm: JSON with {"joint_positions": [...], "timestamp": ...}

            if event_id == "main_follower_joint":
                # Follower arm sends JSON-encoded data
                try:
                    json_str = buffer_bytes.decode('utf-8')
                    feedback = json.loads(json_str)
                    data = feedback.get("joint_positions", [])
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    # If JSON parsing fails, skip this message
                    continue
            else:
                # Leader arm sends raw numpy array
                # Check if buffer size is valid for float32 (must be multiple of 4)
                if len(buffer_bytes) % 4 != 0:
                    continue
                data = np.frombuffer(buffer_bytes, dtype=np.float32).tolist()

            with lock:
                recv_joint[event_id] = data

        except zmq.Again:
            time.sleep(0.001)
        except Exception as e:
            if running_recv_joint_server:
                # Only print errors occasionally to avoid spam
                pass


class LeaderX5Manipulator:
    """
    Leader X5 Manipulator - Leader-Follower teleoperation
    
    Data flow:
    - Leader arm (Feetech) → arm_leader → adapter → follower
    - Follower arm (ARX-X5) → arm_follower_x5 → zeromq
    - Cameras → camera_top/wrist → zeromq → LeaderX5Manipulator
    """

    robot_type = "leader_x5"

    def __init__(self, config: LeaderX5RobotConfig):
        self.config = config
        self.is_connected_flag = False

        # Camera configuration
        self.cameras = {}
        self.camera_names = list(config.cameras.keys())

        # For compatibility with daemon.py logging
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

        # Leader arm state (7 joints: 6 + gripper)
        features["observation.state"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "gripper"],
        }

        # Action features (commands sent to follower ARX-X5)
        features["action"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "gripper"],
        }

        return features

    @property
    def action_features(self) -> dict:
        """Return action features in hardware format for hw_to_dataset_features conversion"""
        # Hardware format: {'joint_0': float, 'joint_1': float, ...}
        return {f"joint_{i}": float for i in range(6)} | {"gripper": float}

    @property
    def observation_features(self) -> dict:
        """Return observation features in hardware format for hw_to_dataset_features conversion"""
        # Hardware format:
        # - Motors: {'joint_0': float, 'joint_1': float, ...}
        # - Cameras: {'top': (height, width, channels), 'wrist': (height, width, channels)}
        motor_features = {f"joint_{i}": float for i in range(6)} | {"gripper": float}
        camera_features = {name: (480, 640, 3) for name in self.camera_names}
        return {**motor_features, **camera_features}

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
        return self.is_connected_flag and _image_connected and _joint_connected

    def connect(self):
        """Connect to DORA dataflow via ZeroMQ"""
        if self.is_connected_flag:
            raise Exception("Leader X5 Manipulator already connected")

        print("[Leader X5] Connecting to DORA dataflow via ZeroMQ...")

        # Initialize ZeroMQ sockets
        _init_zmq()

        # Start receiver threads
        global running_recv_image_server, running_recv_joint_server
        running_recv_image_server = True
        running_recv_joint_server = True

        thread_image = threading.Thread(target=recv_image_server, daemon=True)
        thread_joint = threading.Thread(target=recv_joint_server, daemon=True)

        thread_image.start()
        thread_joint.start()

        self.recv_threads = [thread_image, thread_joint]

        # Wait for connections
        print("[Leader X5] Waiting for data streams...")
        timeout = 30
        start_time = time.time()
        while time.time() - start_time < timeout:
            if _image_connected and _joint_connected:
                break
            time.sleep(0.5)

        if not (_image_connected and _joint_connected):
            error_msg = f"[Leader X5] ERROR: Streams not connected after {timeout}s timeout"
            print(error_msg)
            print(f"  Image stream: {'✓ Connected' if _image_connected else '✗ Not connected'}")
            print(f"  Joint stream: {'✓ Connected' if _joint_connected else '✗ Not connected'}")
            print("\nPossible causes:")
            print("  1. DORA dataflow not running or not ready")
            print("  2. ZeroMQ sockets not created by dora_zeromq.py")
            print("  3. Network/IPC communication issues")
            raise RobotDeviceNotConnectedError(error_msg)

        self.is_connected_flag = True
        print("[Leader X5] Connected to DORA dataflow")

    def run_calibration(self):
        """Leader X5 doesn't need calibration (handled by DORA nodes)"""
        print("[Leader X5] Calibration not needed (handled by DORA nodes)")

    def teleop_step(self, record_data=False):
        """
        Perform one teleoperation step
        Returns (observation_dict, action_dict) if record_data=True

        Format matches SO101Manipulator for compatibility with build_dataset_frame:
        - obs_dict: {'joint_0': float, 'joint_1': float, ..., 'top': image, 'wrist': image}
        - action_dict: {'joint_0': float, 'joint_1': float, ..., 'gripper': float}
        """
        if not self.is_connected:
            raise RobotDeviceNotConnectedError("Leader X5 Manipulator not connected")

        if not record_data:
            return None

        obs_dict = {}
        action_dict = {}

        with lock:
            # Capture images (use camera name as key, not observation.images.xxx)
            for camera_name in self.camera_names:
                event_id = f"image_{camera_name}"
                if event_id in recv_images:
                    obs_dict[camera_name] = recv_images[event_id].copy()

            # Capture leader arm state (flatten to individual joint keys)
            if "main_leader_joint" in recv_joint:
                leader_data = recv_joint["main_leader_joint"]
                if isinstance(leader_data, list) and len(leader_data) >= 7:
                    for i in range(6):
                        obs_dict[f"joint_{i}"] = float(leader_data[i])
                    obs_dict["gripper"] = float(leader_data[6])

            # Capture action (commands sent to follower ARX-X5)
            if "main_follower_joint" in recv_joint:
                follower_data = recv_joint["main_follower_joint"]
                if isinstance(follower_data, list) and len(follower_data) >= 7:
                    for i in range(6):
                        action_dict[f"joint_{i}"] = float(follower_data[i])
                    action_dict["gripper"] = float(follower_data[6])

        # DEBUG: Log captured data (only every 100 calls to avoid spam)
        if not hasattr(self, '_teleop_call_count'):
            self._teleop_call_count = 0
        self._teleop_call_count += 1

        if self._teleop_call_count % 100 == 0:
            print(f"[LeaderX5] DEBUG teleop_step #{self._teleop_call_count}:")
            print(f"  obs_dict keys: {list(obs_dict.keys())}")
            print(f"  action_dict keys: {list(action_dict.keys())}")
            if obs_dict:
                print(f"  Sample obs: joint_0={obs_dict.get('joint_0', 'N/A')}, has images: {any('top' in k or 'wrist' in k for k in obs_dict.keys())}")
            if action_dict:
                print(f"  Sample action: joint_0={action_dict.get('joint_0', 'N/A')}")

        return obs_dict, action_dict

    def capture_observation(self):
        """Capture current observation from all sensors"""
        observation = {}

        with lock:
            # Capture images
            for camera_name in self.camera_names:
                event_id = f"image_{camera_name}"
                if event_id in recv_images:
                    observation[f"observation.images.{camera_name}"] = recv_images[event_id].copy()

            # Capture leader arm state
            if "main_leader_joint" in recv_joint:
                leader_data = recv_joint["main_leader_joint"]
                if isinstance(leader_data, list):
                    observation["observation.state"] = np.array(leader_data[:7], dtype=np.float32)

            # Capture action (commands sent to follower ARX-X5)
            if "main_follower_joint" in recv_joint:
                follower_data = recv_joint["main_follower_joint"]
                if isinstance(follower_data, list):
                    observation["action"] = np.array(follower_data[:7], dtype=np.float32)

        return observation

    def send_action(self, action):
        """
        Send action to robot
        Note: For Leader X5, actions are sent by DORA nodes, not by this class
        """
        print("[Leader X5] Warning: send_action() not implemented (actions handled by DORA nodes)")

    def disconnect(self):
        """Disconnect from DORA dataflow"""
        if not self.is_connected_flag:
            return

        print("[Leader X5] Disconnecting from DORA dataflow...")

        # Stop receiver threads
        global running_recv_image_server, running_recv_joint_server
        running_recv_image_server = False
        running_recv_joint_server = False

        # Wait for threads to finish
        for thread in self.recv_threads:
            thread.join(timeout=2.0)

        # Clean up ZeroMQ
        _cleanup_zmq()

        self.is_connected_flag = False
        print("[Leader X5] Disconnected")

    @property
    def use_videos(self) -> bool:
        return self.config.use_videos

    @property
    def microphones(self) -> dict:
        return {}  # No microphones for Leader X5
