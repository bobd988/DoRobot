#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARX X5 机械臂 Dora 驱动节点
接收关节命令，控制X5机械臂
"""

import json
import os
import sys
import time
import numpy as np
from typing import Any, Optional, List
from contextlib import contextmanager

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node

# 添加X5 SDK路径
sdk_path = os.environ.get("X5_SDK_PATH", "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python")
sys.path.insert(0, sdk_path)

# 设置环境变量
lib_paths = [
    f"{sdk_path}/bimanual/api/arx_x5_src",
    f"{sdk_path}/bimanual/api",
    f"{sdk_path}/bimanual/lib/arx_x5_src",
    f"{sdk_path}/bimanual/lib",
    "/usr/local/lib"
]
os.environ['LD_LIBRARY_PATH'] = ":".join(lib_paths)

# 在导入C++库之前，重定向stdout到stderr
# 这样C++库的输出会被重定向，但不会影响我们的日志
# 保存原始stdout
original_stdout_fd = sys.stdout.fileno()
saved_stdout_fd = os.dup(original_stdout_fd)

# 将stdout重定向到stderr（这样C++库的输出会去stderr）
stderr_fd = sys.stderr.fileno()
os.dup2(stderr_fd, original_stdout_fd)

from bimanual import SingleArm

# 恢复stdout
os.dup2(saved_stdout_fd, original_stdout_fd)
os.close(saved_stdout_fd)
sys.stdout = os.fdopen(original_stdout_fd, 'w', buffering=1)


@contextmanager
def suppress_stdout():
    """临时重定向stdout到/dev/null，用于屏蔽C++库的输出"""
    old_stdout = sys.stdout
    try:
        with open(os.devnull, 'w') as devnull:
            sys.stdout = devnull
            yield
    finally:
        sys.stdout = old_stdout


def extract_bytes(value: Any) -> Optional[bytes]:
    """从Dora值中提取字节数据"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
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

    if isinstance(value, pa.Scalar):
        item = value.as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return str(item).encode("utf-8")

    return None


def extract_float_list(value: Any) -> Optional[List[float]]:
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

    raw = extract_bytes(value)
    if not raw:
        return None

    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    if isinstance(obj, list):
        try:
            return [float(x) for x in obj]
        except Exception:
            return None

    if isinstance(obj, dict):
        # 尝试从字典中提取关节数据
        for k in ("joint", "joints", "q", "angles", "positions", "pos", "joint_positions"):
            v = obj.get(k)
            if isinstance(v, list) and len(v) >= 6:
                try:
                    return [float(x) for x in v]
                except Exception:
                    return None

    return None


def main() -> None:
    node = Node()

    # 配置参数
    can_port = os.environ.get("CAN_PORT", "can0")
    arm_type = int(os.environ.get("ARM_TYPE", "0"))
    num_joints = int(os.environ.get("NUM_JOINTS", "6"))
    dt = float(os.environ.get("DT", "0.05"))

    # 夹爪映射参数
    gripper_scale = float(os.environ.get("GRIPPER_SCALE", "2.0"))  # VR扳机(0-1) -> X5夹爪(0-2.0)

    # 日志控制
    log_every_n = int(os.environ.get("LOG_EVERY_N", "50"))  # 每N次打印一次日志

    print(f"[robot_driver_arx_x5] Initializing ARX X5...", flush=True)
    print(f"  CAN Port: {can_port}", flush=True)
    print(f"  Arm Type: {arm_type}", flush=True)
    print(f"  Num Joints: {num_joints}", flush=True)

    # 初始化X5机械臂
    arm_config = {
        "can_port": can_port,
        "type": arm_type,
        "num_joints": num_joints,
        "dt": dt
    }

    try:
        arm = SingleArm(arm_config)
        print(f"[robot_driver_arx_x5] ✓ ARX X5 initialized successfully", flush=True)
        time.sleep(2)
    except Exception as e:
        print(f"[robot_driver_arx_x5] ✗ Failed to initialize ARX X5: {e}", flush=True)
        return

    # 获取初始状态
    try:
        initial_joints = arm.get_joint_positions()
        print(f"[robot_driver_arx_x5] Initial joint positions: {initial_joints}", flush=True)

        # 发送初始关节反馈给IK节点（解决启动时的鸡生蛋问题）
        feedback = {
            "joint_positions": initial_joints.tolist() if hasattr(initial_joints, 'tolist') else list(initial_joints),
            "timestamp": time.time()
        }
        feedback_bytes = json.dumps(feedback).encode("utf-8")
        node.send_output("joint", feedback_bytes, {})
        print(f"[robot_driver_arx_x5] ✓ Sent initial joint feedback to IK node", flush=True)
    except Exception as e:
        print(f"[robot_driver_arx_x5] Warning: Could not get initial joint positions: {e}", flush=True)

    cmd_count = 0
    last_gripper = 0.0

    for event in node:
        et = event.get("type")
        eid = event.get("id")

        if et == "STOP":
            print(f"[robot_driver_arx_x5] Received STOP signal", flush=True)
            break

        if et != "INPUT":
            continue

        # 处理关节命令
        if eid == "action_joint":
            # IK节点发送的是 PyArrow 数组: [joint1, joint2, joint3, joint4, joint5, gripper]
            joint_data = extract_float_list(event.get("value"))
            if not joint_data or len(joint_data) < num_joints + 1:
                continue

            # 前 num_joints 个是关节角度（度），最后一个是夹爪值（0-100）
            joint_positions = joint_data[:num_joints]
            gripper = joint_data[num_joints] / 100.0  # 转换为 0-1 范围

            try:
                # 控制机械臂关节
                # IK发送的是度（degrees），需要转换为弧度（radians）
                joint_array_rad = np.array([np.deg2rad(x) for x in joint_positions[:num_joints]])
                arm.set_joint_positions(joint_array_rad)

                # 控制夹爪（映射VR扳机值0-1到X5夹爪值0-2.0）
                gripper_x5 = float(gripper) * gripper_scale
                arm.set_catch_pos(pos=gripper_x5)

                cmd_count += 1

                # 定期打印日志
                if cmd_count % log_every_n == 0:
                    print(f"[robot_driver_arx_x5] Cmd #{cmd_count}: joints_deg={joint_positions[:3]}... joints_rad={joint_array_rad[:3].tolist()}... gripper={gripper:.2f}", flush=True)

                # 夹爪变化时打印
                if abs(gripper - last_gripper) > 0.1:
                    print(f"[robot_driver_arx_x5] Gripper changed: {last_gripper:.2f} -> {gripper:.2f}", flush=True)
                    last_gripper = gripper

                # 发送反馈（当前关节位置）
                try:
                    current_joints = arm.get_joint_positions()
                    feedback = {
                        "joint_positions": current_joints.tolist() if hasattr(current_joints, 'tolist') else list(current_joints),
                        "timestamp": time.time()
                    }
                    feedback_bytes = json.dumps(feedback).encode("utf-8")
                    node.send_output("joint", feedback_bytes, event.get("metadata", {}) or {})
                except Exception as e:
                    if cmd_count % log_every_n == 0:
                        print(f"[robot_driver_arx_x5] Warning: Could not send feedback: {e}", flush=True)

            except Exception as e:
                print(f"[robot_driver_arx_x5] Control failed: {e}", flush=True)
                import traceback
                traceback.print_exc()

    print(f"[robot_driver_arx_x5] Shutting down...", flush=True)
    print(f"[robot_driver_arx_x5] Total commands processed: {cmd_count}", flush=True)


if __name__ == "__main__":
    main()
