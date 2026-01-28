#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional, List

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node

import pybullet as p
import pybullet_data


# ---------- utils ----------
def extract_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
        if pa.types.is_uint8(value.type) or pa.types.is_int8(value.type):
            return bytes(value.to_pylist())
        item = value[0].as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return json.dumps(item).encode("utf-8")

    if isinstance(value, pa.Scalar):
        item = value.as_py()
        if item is None:
            return None
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return json.dumps(item).encode("utf-8")

    return None


def deg2rad(x: float) -> float:
    return x * 3.141592653589793 / 180.0


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


# ---------- config ----------
URDF_PATH = os.environ.get(
    "SIM_URDF",
    "/home/demo/synk/dora-dorobot/operating_platform/teleop_vr/urdf/SO100/so100.urdf",
)

# 符号翻转：解决“右变左”的常见问题（通常是 pan 轴）
PAN_SIGN   = float(os.environ.get("SIM_PAN_SIGN", "-1"))
LIFT_SIGN  = float(os.environ.get("SIM_LIFT_SIGN", "1"))
ELBOW_SIGN = float(os.environ.get("SIM_ELBOW_SIGN", "1"))
WFLEX_SIGN = float(os.environ.get("SIM_WFLEX_SIGN", "1"))
WROLL_SIGN = float(os.environ.get("SIM_WROLL_SIGN", "1"))

# gripper 映射：兼容 0..1 / 0..45deg / 0..100
GRIPPER_MAX_DEG = float(os.environ.get("SIM_GRIPPER_MAX_DEG", "45"))
GRIPPER_MAX_RAD = float(os.environ.get("SIM_GRIPPER_MAX_RAD", "1.2"))  # joint6 upper=2.0 rad，先保守

TICK_HZ = float(os.environ.get("SIM_TICK_HZ", "50"))
PB_DT = 1.0 / 240.0


def main():
    node = Node()

    urdf_path = Path(URDF_PATH).resolve()
    urdf_dir = urdf_path.parent

    p.connect(p.GUI)
    p.setAdditionalSearchPath(str(pybullet_data.getDataPath()))
    p.setAdditionalSearchPath(str(urdf_dir))  # ✅ 关键：让 assets/*.stl 找得到
    p.resetSimulation()
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(PB_DT)

    plane_path = os.path.join(pybullet_data.getDataPath(), "plane.urdf")
    p.loadURDF(plane_path, [0, 0, -0.2])

    # 让镜头对准原点（否则模型可能在视野外）
    p.resetDebugVisualizerCamera(
        cameraDistance=0.8,
        cameraYaw=60,
        cameraPitch=-25,
        cameraTargetPosition=[0, 0, 0.15],
    )

    robot_id = p.loadURDF(str(urdf_path), useFixedBase=True)
    print(f"[sim_viz] ✅ loaded URDF: {urdf_path}", flush=True)

    # jointName -> jointIndex
    name2idx: Dict[str, int] = {}
    for j in range(p.getNumJoints(robot_id)):
        info = p.getJointInfo(robot_id, j)
        jname = info[1].decode("utf-8")
        name2idx[jname] = j

    # URDF joint 名是 "1".."6"
    joint_map = [
        ("1", "shoulder_pan.pos", PAN_SIGN),
        ("2", "shoulder_lift.pos", LIFT_SIGN),
        ("3", "elbow_flex.pos", ELBOW_SIGN),
        ("4", "wrist_flex.pos", WFLEX_SIGN),
        ("5", "wrist_roll.pos", WROLL_SIGN),
        ("6", "gripper.pos", 1.0),
    ]

    joint_indices: List[int] = []
    for jname, _, _ in joint_map:
        if jname not in name2idx:
            raise RuntimeError(f"[sim_viz] URDF missing joint name={jname}")
        joint_indices.append(name2idx[jname])

    print("[sim_viz] ✅ listening inputs: tick + (action_joint OR joint_cmd_left)", flush=True)

    latest_action: Optional[Dict[str, float]] = None
    last_wait_log = 0.0
    last_alive_log = 0.0

    steps_per_tick = max(1, int(round((1.0 / TICK_HZ) / PB_DT)))  # 50Hz -> ~5 steps

    for event in node:
        et = event.get("type")
        eid = event.get("id")

        if et == "STOP":
            break

        # 1) 直接吃 action_joint（float array）：[pan,lift,elbow,wflex,wroll,gripper]
        if et == "INPUT" and eid == "action_joint":
            try:
                arr = event["value"].to_numpy()
                if arr is None or len(arr) < 6:
                    continue
                latest_action = {
                    "shoulder_pan.pos": float(arr[0]),
                    "shoulder_lift.pos": float(arr[1]),
                    "elbow_flex.pos": float(arr[2]),
                    "wrist_flex.pos": float(arr[3]),
                    "wrist_roll.pos": float(arr[4]),
                    "gripper.pos": float(arr[5]),
                }
            except Exception:
                continue

        # 2) 兼容旧链路：joint_cmd_left（JSON bytes）
        if et == "INPUT" and eid == "joint_cmd_left":
            raw = extract_bytes(event.get("value"))
            if not raw:
                continue
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                continue

            # 兼容 wrapper / pure action
            if isinstance(payload, dict) and "action" in payload and isinstance(payload["action"], dict):
                if not bool(payload.get("enable", True)):
                    latest_action = None
                else:
                    latest_action = payload["action"]
            elif isinstance(payload, dict):
                latest_action = payload

        # tick：推进仿真并渲染
        if et == "INPUT" and eid == "tick":
            for _ in range(steps_per_tick):
                p.stepSimulation()

            now = time.time()

            if not latest_action:
                if now - last_wait_log > 1.5:
                    print("[sim_viz] waiting for action_joint / joint_cmd_left ...", flush=True)
                    last_wait_log = now
                continue

            targets = []
            for _, key, sign in joint_map:
                v = float(latest_action.get(key, 0.0))

                if key == "gripper.pos":
                    # 支持：0..1 / 0..45deg / 0..100
                    if v <= 1.0:
                        g = clamp(v, 0.0, 1.0)
                    elif v <= 100.0:
                        g = clamp(v / 100.0, 0.0, 1.0)
                    else:
                        g = clamp(v / GRIPPER_MAX_DEG, 0.0, 1.0)
                    rad = g * GRIPPER_MAX_RAD
                else:
                    rad = sign * deg2rad(v)

                targets.append(rad)

            p.setJointMotorControlArray(
                bodyUniqueId=robot_id,
                jointIndices=joint_indices,
                controlMode=p.POSITION_CONTROL,
                targetPositions=targets,
                forces=[5.0] * len(targets),
            )

            if now - last_alive_log > 1.0:
                pan_deg = latest_action.get("shoulder_pan.pos", 0.0)
                print(f"[sim_viz] alive pan={pan_deg:.1f}deg (sign={PAN_SIGN:+.0f})", flush=True)
                last_alive_log = now

    p.disconnect()


if __name__ == "__main__":
    main()
