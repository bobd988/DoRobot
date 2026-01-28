#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
from typing import Any, Dict, Optional, Tuple, List

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node

import pybullet as pb
import pybullet_data


# ----------------------------
# bytes extraction (dora value)
# ----------------------------
def extract_bytes(value: Any) -> Optional[bytes]:
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


# ----------------------------
# helpers
# ----------------------------
def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def rad2deg(x: float) -> float:
    return x * 57.29577951308232



def deg2rad(x: float) -> float:
    return x * 0.017453292519943295





def extract_float_list(value: Any) -> Optional[List[float]]:
    """Best-effort parse for dora INPUT value that may be pa.Array, bytes(JSON), or list-like JSON."""
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
        for k in ("joint", "joints", "q", "angles", "positions", "pos"):
            v = obj.get(k)
            if isinstance(v, list) and len(v) >= 5:
                try:
                    return [float(x) for x in v]
                except Exception:
                    return None

    return None


def load_calibration(calib_path: str) -> Optional[Dict[str, Any]]:
    if not calib_path:
        return None
    try:
        with open(calib_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def ticks_to_deg(ticks: float, cfg: Dict[str, Any]) -> float:
    """Convert raw servo ticks (0..4095) to degrees using homing_offset and range clamp."""
    t = float(ticks)
    rmin = cfg.get("range_min")
    rmax = cfg.get("range_max")
    if rmin is not None:
        t = max(t, float(rmin))
    if rmax is not None:
        t = min(t, float(rmax))
    off = float(cfg.get("homing_offset", 0.0))
    # assume 12-bit position mapping: 0..4095 -> 0..360deg
    deg = (t - off) * (360.0 / 4096.0)
    drive_mode = int(cfg.get("drive_mode", 0) or 0)
    # heuristic: some firmwares flip sign via drive_mode; if you find it's inverted, you can also use JOINT_SIGN to fix.
    if drive_mode in (1, 2):
        deg = -deg
    return deg


def normalize_joint_input(vals: List[float], calib: Optional[Dict[str, Any]]) -> Tuple[Optional[List[float]], str]:
    """Return first 5 joints in radians. Heuristic: ticks -> deg using calib; else deg/rad."""
    if len(vals) < 5:
        return None, "insufficient"
    v5 = [float(x) for x in vals[:5]]
    mx = max(abs(x) for x in v5) if v5 else 0.0

    if mx > 400.0:
        # likely raw ticks
        if not calib:
            return None, "ticks(no_calib)"
        order = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
        degs: List[float] = []
        for i, name in enumerate(order):
            cfg = calib.get(name)
            if not isinstance(cfg, dict):
                return None, f"ticks(calib_missing:{name})"
            degs.append(ticks_to_deg(v5[i], cfg))
        return [deg2rad(d) for d in degs], "ticks"
    if mx > 20.0:
        # degrees
        return [deg2rad(x) for x in v5], "deg"
    return v5, "rad"


def parse_floats(s: str, n: int, default: List[float]) -> List[float]:
    try:
        parts = [p.strip() for p in s.split(",")]
        vals = [float(p) for p in parts[:n]]
        if len(vals) != n:
            return default
        return vals
    except Exception:
        return default


def parse_axis_map(s: str) -> List[Tuple[int, float]]:
    tok = [t.strip() for t in s.split(",")]
    if len(tok) != 3:
        tok = ["x", "y", "z"]

    def one(t: str) -> Tuple[int, float]:
        sign = -1.0 if t.startswith("-") else 1.0
        a = t[1:] if t.startswith("-") else t
        a = a.lower()
        if a == "x":
            return (0, sign)
        if a == "y":
            return (1, sign)
        if a == "z":
            return (2, sign)
        return (0, sign)

    return [one(tok[0]), one(tok[1]), one(tok[2])]


def apply_map(v: List[float], m: List[Tuple[int, float]]) -> List[float]:
    return [m[0][1] * v[m[0][0]], m[1][1] * v[m[1][0]], m[2][1] * v[m[2][0]]]


def find_link_index(body: int, link_name: str) -> int:
    n = pb.getNumJoints(body)
    for j in range(n):
        info = pb.getJointInfo(body, j)
        child_link_name = info[12].decode("utf-8", errors="ignore")
        if child_link_name == link_name:
            return j
    raise RuntimeError(f"End-effector link '{link_name}' not found in URDF joints.")


def collect_joint_limits(body: int, joint_ids: List[int]) -> Tuple[List[float], List[float], List[float]]:
    lower, upper, ranges = [], [], []
    for jid in joint_ids:
        info = pb.getJointInfo(body, jid)
        lo = float(info[8])
        hi = float(info[9])
        if hi <= lo:
            lo, hi = -3.14159, 3.14159
        lower.append(lo)
        upper.append(hi)
        ranges.append(hi - lo)
    return lower, upper, ranges


# ----------------------------
# main
# ----------------------------
def main() -> None:
    # ---- config ----
    urdf_path = os.environ.get(
        "URDF_PATH",
        "/home/demo/synk/lerobot-main/telegrip-main/URDF/SO100/so100.urdf",
    )
    ee_link = os.environ.get("EE_LINK", "Fixed_Jaw_tip")

    #机械臂的初始位置
    home_pos_base = parse_floats(os.environ.get("IK_HOME_POS", "0.20,0.00,0.25"), 3, [0.20, 0.0, 0.25])
    home_pos = home_pos_base[:]

    pos_map = parse_axis_map(os.environ.get("IK_POS_MAP", "x,y,z"))
    pos_scale = parse_floats(os.environ.get("IK_POS_SCALE", "1,1,1"), 3, [1.0, 1.0, 1.0])

    ik_iters = int(float(os.environ.get("IK_ITERS", "80")))
    ik_thresh = float(os.environ.get("IK_THRESH", "1e-4"))
    min_dt = float(os.environ.get("IK_SEND_DT", "0.02"))  # 建议 50Hz/30Hz都行

    heartbeat_sec = float(os.environ.get("LOG_HEARTBEAT_SEC", "2"))
    require_joint_on_enable = bool(int(os.environ.get("IK_REQUIRE_JOINT_ON_ENABLE", "1")))
    calib = load_calibration(os.environ.get("CALIB_PATH", ""))

    # 关节符号/偏置
    joint_sign = parse_floats(os.environ.get("JOINT_SIGN", "1,1,1,1,1"), 5, [1, 1, 1, 1, 1])
    joint_offset_deg = parse_floats(os.environ.get("JOINT_OFFSET_DEG", "0,0,0,0,0"), 5, [0, 0, 0, 0, 0])

    # ---- dora ----
    node = Node()
    print("[arm_to_jointcmd_ik] ready", flush=True)
    print(f"[arm_to_jointcmd_ik] urdf={urdf_path} ee_link={ee_link}", flush=True)

    # ---- pybullet init ----
    pb.connect(pb.DIRECT)
    pb.setAdditionalSearchPath(pybullet_data.getDataPath())
    pb.setGravity(0, 0, -9.81)

    body = pb.loadURDF(urdf_path, useFixedBase=True, flags=pb.URDF_USE_INERTIA_FROM_FILE)
    ee_idx = find_link_index(body, ee_link)

    # IK joints：1..5 -> bullet index 0..4
    ik_joint_ids = [0, 1, 2, 3, 4]
    lower, upper, ranges = collect_joint_limits(body, ik_joint_ids)

    rest = [0.0, -0.3, -1.0, 1.0, 0.0]
    last_sol = rest[:]

    last_enable: Optional[bool] = None
    vr_home_pos: Optional[List[float]] = None
    last_joint_rad: Optional[List[float]] = None
    last_joint_unit: str = ""
    printed_initial_pose: bool = False
    clutched: bool = False

    last_send = 0.0
    last_hb = time.time()

    for event in node:
        et = event.get("type")
        if et == "STOP":
            break
        if et != "INPUT":
            continue

        eid = event.get("id")
        if eid == "joint":
            vals = extract_float_list(event.get("value"))
            if vals:
                jrad, unit = normalize_joint_input(vals, calib)
                if jrad is not None:
                    last_joint_rad = jrad
                    last_joint_unit = unit
                    if not printed_initial_pose:
                        try:
                            for i in range(5):
                                pb.resetJointState(body, ik_joint_ids[i], float(last_joint_rad[i]))
                            ls = pb.getLinkState(body, ee_idx)
                            ee_world = ls[0]
                            print(
                                f"[arm_to_jointcmd_ik] initial_joint_unit={last_joint_unit} "
                                f"joints(rad)={[round(x,4) for x in last_joint_rad]} "
                                f"ee_xyz={tuple(round(float(x),4) for x in ee_world)}",
                                flush=True,
                            )
                        except Exception as e:
                            print(f"[arm_to_jointcmd_ik] WARN: initial pose compute failed: {e}", flush=True)
                        printed_initial_pose = True
            continue

        if eid != "arm_cmd":
            continue

        raw = extract_bytes(event.get("value"))
        if not raw:
            continue

        try:
            cmd: Dict[str, Any] = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"[arm_to_jointcmd_ik] json decode failed: {e}; head={raw[:120]!r}", flush=True)
            continue

        if cmd.get("arm") not in (None, "left"):  # 兼容你之前 left 逻辑
            continue

        enable = bool(cmd.get("enable", False))
        gripper = float(cmd.get("gripper", 0.0))
        ee_pose = cmd.get("ee_pose") or {}
        vr_pos = ee_pose.get("pos", [0.0, 0.0, 0.0])

        if last_enable is None or enable != last_enable:
            print(f"[arm_to_jointcmd_ik] enable changed: {last_enable} -> {enable}", flush=True)
            last_enable = enable
            clutched = False
            if enable:
                vr_home_pos = [float(vr_pos[0]), float(vr_pos[1]), float(vr_pos[2])]
                rest = last_sol[:]
            else:
                vr_home_pos = None
                home_pos = home_pos_base[:]

        if heartbeat_sec > 0:
            now = time.time()
            if now - last_hb >= heartbeat_sec:
                print(f"[arm_to_jointcmd_ik] heartbeat enable={enable} gripper={gripper:.2f}", flush=True)
                last_hb = now

        if not enable or vr_home_pos is None:
            continue

        # ---- clutch on enable: bind IK home/rest to current real joints so delta=0 does not move ----
        if not clutched:
            if last_joint_rad is None:
                if require_joint_on_enable:
                    continue
            else:
                try:
                    for i in range(5):
                        pb.resetJointState(body, ik_joint_ids[i], float(last_joint_rad[i]))
                    last_sol = [float(x) for x in last_joint_rad]
                    rest = last_sol[:]
                    ls = pb.getLinkState(body, ee_idx)
                    ee_world = ls[0]
                    home_pos = [float(ee_world[0]), float(ee_world[1]), float(ee_world[2])]
                    clutched = True
                    print(
                        f"[arm_to_jointcmd_ik] clutched home_pos={tuple(round(x,4) for x in home_pos)} "
                        f"joint_unit={last_joint_unit}",
                        flush=True,
                    )
                except Exception as e:
                    print(f"[arm_to_jointcmd_ik] WARN: clutch failed: {e}", flush=True)
                    if require_joint_on_enable:
                        continue

        now = time.time()
        if now - last_send < min_dt:
            continue

        # ---- build target position ----
        dx = float(vr_pos[0]) - vr_home_pos[0]
        dy = float(vr_pos[1]) - vr_home_pos[1]
        dz = float(vr_pos[2]) - vr_home_pos[2]
        d = [dx, dy, dz]
        d_mapped = apply_map(d, pos_map)
        d_scaled = [d_mapped[0] * pos_scale[0], d_mapped[1] * pos_scale[1], d_mapped[2] * pos_scale[2]]

        target_pos = [home_pos[0] + d_scaled[0], home_pos[1] + d_scaled[1], home_pos[2] + d_scaled[2]]

        # ---- IK ----
        try:
            sol = pb.calculateInverseKinematics(
                bodyUniqueId=body,
                endEffectorLinkIndex=ee_idx,
                targetPosition=target_pos,
                lowerLimits=lower,
                upperLimits=upper,
                jointRanges=ranges,
                restPoses=rest,
                maxNumIterations=ik_iters,
                residualThreshold=ik_thresh,
            )
        except Exception as e:
            print(f"[arm_to_jointcmd_ik] IK failed: {e}", flush=True)
            continue

        j = [float(sol[i]) for i in range(5)]
        for i in range(5):
            j[i] = clamp(j[i], lower[i], upper[i])

        last_sol = j[:]
        rest = j[:]

        # ---- output: action_joint (pa.float32[6]) ----
        # 前 5 个：deg + sign + offset
        q_deg = []
        for i in range(5):
            v = rad2deg(j[i])
            v = v * float(joint_sign[i]) + float(joint_offset_deg[i])
            q_deg.append(float(v))

        # gripper：0..1 -> 0..100
        g01 = clamp(gripper, 0.0, 1.0)
        g_0_100 = float(g01 * 100.0)

        out_arr = pa.array(
            [q_deg[0], q_deg[1], q_deg[2], q_deg[3], q_deg[4], g_0_100],
            type=pa.float32(),
        )

        node.send_output("action_joint", out_arr, event.get("metadata", {}) or {})
        print(f"[arm_to_jointcmd_ik] SENT action_joint pan={q_deg[0]:.1f} grip={g_0_100:.0f}", flush=True)
        last_send = now

    pb.disconnect()


if __name__ == "__main__":
    main()
