#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
from typing import Any, Dict, Optional

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

        # 兼容：如果是“整数数组”（uint8/int8/int64...），按字节拼回 bytes
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


def _to_ts_seconds(vr: dict) -> float:
    # Telegrip: timestamp=Date.now() (ms)
    if "ts" in vr:
        try:
            return float(vr["ts"])
        except Exception:
            pass
    if "timestamp" in vr:
        try:
            return float(vr["timestamp"]) / 1000.0
        except Exception:
            pass
    return 0.0


def main() -> None:
    node = Node()

    # ---- logging controls ----
    # 0 = 完全不打印心跳，只打印状态变化；>0 = 每隔 N 秒打印一次心跳
    heartbeat_sec = float(os.environ.get("MUX_HEARTBEAT_SEC", "5.0"))
    # gripper 的“变化阈值”，避免 0.0001 这种抖动触发变化打印
    grip_eps = float(os.environ.get("MUX_GRIP_EPS", "0.05"))

    last_enable: Optional[bool] = None
    last_gripper: Optional[float] = None
    last_hb_t = 0.0

    for event in node:
        if event.get("type") == "STOP":
            break
        if event.get("type") != "INPUT":
            continue
        if event.get("id") != "vr_event":
            continue

        raw = extract_bytes(event.get("value"))
        if not raw:
            continue

        try:
            vr = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print("[command_mux] json decode failed:", e, "head=", raw[:120], flush=True)
            continue

        # --- 兼容 Telegrip vr_app.js 格式 + 你自定义格式 ---
        if isinstance(vr.get("left"), dict):
            left = vr.get("left")
            pos = left.get("pos", [0.0, 0.0, 0.0])
            quat = left.get("quat", [0.0, 0.0, 0.0, 1.0])
            enable = bool(left.get("grip", False))
            gripper = float(left.get("trigger", 0.0))
            frame = vr.get("frame", "world")
        elif isinstance(vr.get("leftController"), dict):
            lc = vr["leftController"]
            p = lc.get("position") or {}
            q = lc.get("quaternion") or {}
            pos = [float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 0.0))]
            quat = [float(q.get("x", 0.0)), float(q.get("y", 0.0)), float(q.get("z", 0.0)), float(q.get("w", 1.0))]
            enable = bool(lc.get("gripActive", False))
            gripper = float(lc.get("trigger", 0.0))
            frame = "world"
            # DEBUG: Print first 5 VR events to see grip status
            if not hasattr(main, '_vr_count'):
                main._vr_count = 0
            main._vr_count += 1
            if main._vr_count <= 5:
                print(f"[command_mux] DEBUG VR #{main._vr_count}: gripActive={lc.get('gripActive')}, trigger={gripper:.2f}, pos={pos}", flush=True)
        else:
            continue

        cmd = {
            "ts": _to_ts_seconds(vr),
            "arm": "left",
            "frame": frame,
            "enable": enable,
            "ee_pose": {"pos": pos, "quat": quat},
            "gripper": gripper,
        }

        out = json.dumps(cmd).encode("utf-8")
        node.send_output("arm_cmd", out, event.get("metadata", {}) or {})

        # ---- PRINT POLICY: only on state change (and optional heartbeat) ----
        changed = False
        if last_enable is None or enable != last_enable:
            print(f"[command_mux] enable changed: {last_enable} -> {enable} (gripActive={lc.get('gripActive') if 'lc' in locals() else 'N/A'})", flush=True)
            last_enable = enable
            changed = True

        if last_gripper is None or abs(gripper - last_gripper) > grip_eps:
            # 只有当 enable=true 时更关心 gripper；enable=false 时也可以打印一次变化
            if enable:
                print(f"[command_mux] gripper changed: {last_gripper} -> {gripper:.2f}", flush=True)
                changed = True
            last_gripper = gripper

        if (not changed) and heartbeat_sec > 0:
            now = time.time()
            if now - last_hb_t >= heartbeat_sec:
                print(f"[command_mux] heartbeat enable={enable} gripper={gripper:.2f}", flush=True)
                last_hb_t = now


if __name__ == "__main__":
    main()
