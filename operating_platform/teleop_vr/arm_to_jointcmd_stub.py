#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import Any, Optional, Dict

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


def extract_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
        # UInt8Array -> bytes
        if pa.types.is_uint8(value.type) or pa.types.is_int8(value.type):
            return bytes(value.to_pylist())
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


def main() -> None:
    node = Node()
    print("[arm_to_jointcmd] ready", flush=True)

    last_enable = None
    last_print_t = 0.0
    PRINT_DT = float(__import__("os").environ.get("ARM2J_PRINT_DT", "2.0"))  # 最多2秒打印一次(可调)

    for event in node:
        if event.get("type") == "STOP":
            break
        if event.get("type") != "INPUT":
            continue
        if event.get("id") != "arm_cmd":
            continue

        raw = extract_bytes(event.get("value"))
        if not raw:
            continue

        try:
            cmd: Dict[str, Any] = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"[arm_to_jointcmd] json decode failed: {e}; head={raw[:120]!r}", flush=True)
            continue

        if cmd.get("arm") != "left":
            continue

        enable = bool(cmd.get("enable", False))
        gripper = float(cmd.get("gripper", 0.0))

        # 只在 enable 状态变化时打印一次（尤其是 false->true）
        if last_enable is None or enable != last_enable:
            print(f"[arm_to_jointcmd] enable changed: {last_enable} -> {enable}", flush=True)
            last_enable = enable

        # enable=false：不发动作（更安全）
        if not enable:
            continue

        # 固定姿态验证链路（后面替换成 IK 输出）
        action = {
            "shoulder_pan.pos": 0.0,
            "shoulder_lift.pos": -20.0,
            "elbow_flex.pos": -90.0,
            "wrist_flex.pos": 60.0,
            "wrist_roll.pos": 0.0,
            "gripper.pos": 45.0 if gripper > 0.5 else 0.0,
        }

        out = json.dumps(action).encode("utf-8")
        node.send_output("joint_cmd_left", out, event.get("metadata", {}) or {})

        # 可选：心跳打印（限频），用于确认一直在发
        import time
        now = time.time()
        if now - last_print_t > PRINT_DT:
            print(f"[arm_to_jointcmd] sending... gripper={gripper:.2f}", flush=True)
            last_print_t = now
   


if __name__ == "__main__":
    main()
