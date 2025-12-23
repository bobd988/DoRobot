#!/usr/bin/env python3
"""Reset Piper arm to initial position."""

import os
import sys
import time
from piper_sdk import C_PiperInterface


def enable_arm(piper: C_PiperInterface, timeout: float = 10.0) -> bool:
    """Enable the arm with timeout."""
    enable_flag = all(piper.GetArmEnableStatus())

    if enable_flag:
        print("Arm already enabled")
        return True

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
            print("Tip: Check if arm is in motion or emergency stop is pressed")
            return False

    print(f"Arm enabled successfully ({time.time() - start_time:.2f}s)")
    return True


def main():
    # Initial position to reset to
    initial_position = [5418, -1871, -1770, -8379, 35767, 24018]

    can_bus = os.getenv("CAN_BUS", "")
    if len(sys.argv) > 1:
        can_bus = sys.argv[1]

    print(f"Initializing Piper arm on CAN bus: {can_bus or 'default'}")
    piper = C_PiperInterface(can_bus)
    piper.ConnectPort()

    if not enable_arm(piper):
        sys.exit(1)

    print("Resetting to initial position...")
    print(f"Target: {initial_position}")

    # Set motion speed (30% for safe movement)
    piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)

    # Move to initial position
    piper.JointCtrl(
        initial_position[0],
        initial_position[1],
        initial_position[2],
        initial_position[3],
        initial_position[4],
        initial_position[5],
    )

    print("Reset command sent. Arm moving to initial position.")


if __name__ == "__main__":
    main()
