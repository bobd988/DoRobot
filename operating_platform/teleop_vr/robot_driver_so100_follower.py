#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import builtins
import json
import os
import time
from typing import Any, Dict, Optional

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node

from lerobot.robots.so100_follower.config_so100_follower import SO100FollowerConfig
from lerobot.robots.so100_follower.so100_follower import SO100Follower


REQUIRED_KEYS = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]


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


def normalize_action(payload: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    兼容两种输入：
    A) 纯 action_dict: 直接包含 REQUIRED_KEYS
    B) wrapper: {"enable": bool, "action": {REQUIRED_KEYS...}}
    返回：action_dict（全 float），或 None 表示不发送
    """
    if "action" in payload and isinstance(payload.get("action"), dict):
        enable = bool(payload.get("enable", True))
        if not enable:
            return None
        action = payload["action"]
    else:
        action = payload

    if not all(k in action for k in REQUIRED_KEYS):
        return None

    return {k: float(action[k]) for k in REQUIRED_KEYS}


def main() -> None:
    node = Node()

    left_port = os.environ.get(
        "LEFT_FOLLOWER_PORT",
        "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7C123107-if00",
    )
    print(f"[robot_driver] using LEFT_FOLLOWER_PORT={left_port}", flush=True)

    # ✅ dora node 没有交互 stdin，这里等价“自动按 Enter”
    builtins.input = lambda prompt="": (print(prompt, flush=True) or "")

    cfg = SO100FollowerConfig(
        port=left_port,
        use_degrees=True,
        disable_torque_on_disconnect=True,
    )
    cfg.id = "left_follower"

    robot = SO100Follower(cfg)
    robot.connect()
    print("[robot_driver] ✅ connected", flush=True)

    try:
        obs = robot.get_observation()
        if obs:
            head = {k: obs.get(k) for k in REQUIRED_KEYS}
            print(f"[robot_driver] initial obs: {head}", flush=True)
    except Exception as e:
        print(f"[robot_driver] warn: get_observation failed: {e}", flush=True)

    min_dt = float(os.environ.get("ROBOT_SEND_DT", "0.05"))  # 默认 20Hz
    heartbeat_sec = float(os.environ.get("DRIVER_HEARTBEAT_SEC", "2.0"))  # 0=不打印心跳

    last_send = 0.0
    last_print = 0.0
    sent_count = 0
    warned_invalid_once = False

    try:
        for event in node:
            if event.get("type") != "INPUT":
                continue
            if event.get("id") != "joint_cmd_left":
                continue

            raw = extract_bytes(event.get("value"))
            if not raw:
                continue

            try:
                payload: Dict[str, Any] = json.loads(raw.decode("utf-8"))
            except Exception as e:
                # 只提示一次就行
                if not warned_invalid_once:
                    print(f"[robot_driver] json decode failed: {e}; head={raw[:120]!r}", flush=True)
                    warned_invalid_once = True
                continue

            action_dict = normalize_action(payload)
            if action_dict is None:
                # 只提示一次，避免刷屏
                if (not warned_invalid_once) and (not all(k in payload for k in REQUIRED_KEYS)):
                    print(f"[robot_driver] invalid payload keys: {sorted(payload.keys())}", flush=True)
                    warned_invalid_once = True
                continue

            now = time.time()
            if now - last_send < min_dt:
                continue

            robot.send_action(action_dict)
            last_send = now
            sent_count += 1

            # ---- PRINT POLICY ----
            if sent_count == 1:
                print("[robot_driver] first command sent", flush=True)
                last_print = now
            elif heartbeat_sec > 0 and (now - last_print) >= heartbeat_sec:
                print(f"[robot_driver] sending... pan={action_dict['shoulder_pan.pos']:.1f}", flush=True)
                last_print = now

    finally:
        try:
            robot.disconnect()
        except Exception:
            pass
        print("[robot_driver] disconnected", flush=True)


if __name__ == "__main__":
    main()
