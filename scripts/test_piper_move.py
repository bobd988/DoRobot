#!/usr/bin/env python3
"""Test script to move Piper arm to a target joint position."""

import os
import sys
import time
import argparse
from piper_sdk import C_PiperInterface


def enable_arm(piper: C_PiperInterface, timeout: float = 5.0) -> bool:
    """Enable the arm with timeout."""
    enable_flag = all(piper.GetArmEnableStatus())

    start_time = time.time()
    retry_count = 0

    while not enable_flag:
        enable_flag = piper.EnablePiper()
        retry_count += 1

        if retry_count % 10 == 1:
            print(f"Enabling arm... (attempt {retry_count})")

        time.sleep(0.1)
        if time.time() - start_time > timeout:
            print(f"ERROR: Arm enable timeout after {timeout}s")
            return False

    print(f"Arm enabled successfully ({time.time() - start_time:.2f}s)")
    return True


def move_to_position(piper: C_PiperInterface, target: list[int], speed: int = 30):
    """Move arm to target joint position."""
    if len(target) != 6:
        raise ValueError("Target must have 6 joint values")

    # Set motion speed (30% for safe slow movement)
    piper.MotionCtrl_2(0x01, 0x01, speed, 0x00)

    # Send joint command
    piper.JointCtrl(target[0], target[1], target[2], target[3], target[4], target[5])
    print(f"Moving to: {target}")


def main():
    parser = argparse.ArgumentParser(description="Move Piper arm to target position")
    parser.add_argument(
        "--target",
        type=int,
        nargs=6,
        help="Target joint positions (6 values in 0.001 degree units)",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=30,
        help="Motion speed percentage (default: 30)",
    )
    parser.add_argument(
        "--can-bus",
        type=str,
        default="",
        help="CAN bus interface (default: from CAN_BUS env var)",
    )

    args = parser.parse_args()

    # Safe default target: small movement from initial position
    # Initial: [5418, -1871, -1770, -8379, 35767, 24018]
    # Target: +5000 units (+5.0 degrees) on each joint
    default_target = [10418, 3129, 3230, -3379, 40767, 29018]

    target = args.target if args.target else default_target
    can_bus = args.can_bus or os.getenv("CAN_BUS", "")

    print(f"Initializing Piper arm on CAN bus: {can_bus or 'default'}")
    piper = C_PiperInterface(can_bus)
    piper.ConnectPort()

    if not enable_arm(piper):
        sys.exit(1)

    print(f"Moving to target position (speed: {args.speed}%)...")
    move_to_position(piper, target, args.speed)

    print("Movement command sent. Monitor arm position to verify.")


if __name__ == "__main__":
    main()
