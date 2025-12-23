#!/usr/bin/env python3
"""Test SO101 arm connections"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1'))

from motors.feetech import FeetechMotorsBus
from motors import Motor

def test_port(port_name, port_path):
    """Test connection to a port"""
    print(f"\n{'='*60}")
    print(f"Testing {port_name}: {port_path}")
    print(f"{'='*60}")

    # Check if port exists
    if not os.path.exists(port_path) and not port_path.startswith('can'):
        print(f"❌ Port does not exist: {port_path}")
        return False

    # Try to scan for motors
    print(f"Scanning for motors on {port_path}...")
    try:
        # Create a minimal motor config for scanning
        test_motors = {
            f"motor_{i}": Motor(i, "sts3215", None)
            for i in range(1, 7)
        }

        bus = FeetechMotorsBus(
            port=port_path,
            motors=test_motors,
            calibration=None
        )

        # Try to connect without handshake first
        print("Attempting to open port...")
        if not bus.port_handler.openPort():
            print(f"❌ Failed to open port {port_path}")
            return False

        print(f"✓ Port opened successfully")

        # Scan for motors
        print("Scanning for motor IDs...")
        found_motors = {}
        for motor_id in range(1, 20):  # Scan IDs 1-19
            try:
                model_number = bus.read("Model_Number", motor_id)
                if model_number:
                    found_motors[motor_id] = model_number
                    print(f"  ✓ Found motor ID {motor_id}: model {model_number}")
            except:
                pass

        bus.port_handler.closePort()

        if found_motors:
            print(f"\n✓ Found {len(found_motors)} motor(s)")
            return True
        else:
            print(f"\n❌ No motors found on {port_path}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("SO101 Connection Diagnostic Tool")
    print("="*60)

    # Test leader arm (serial)
    leader_ok = test_port("Leader Arm (Serial)", "/dev/ttyUSB0")

    # Test follower arm (CAN)
    print(f"\n{'='*60}")
    print(f"Testing Follower Arm (CAN): can_left")
    print(f"{'='*60}")
    print("Note: CAN bus testing requires different approach")
    print("Checking if CAN interface exists...")

    import subprocess
    try:
        result = subprocess.run(['ip', 'link', 'show', 'can_left'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ CAN interface 'can_left' exists")
            print(result.stdout)

            # Check if it's UP
            if 'UP' in result.stdout:
                print("✓ CAN interface is UP")
            else:
                print("❌ CAN interface is DOWN")
        else:
            print("❌ CAN interface 'can_left' not found")
    except Exception as e:
        print(f"❌ Error checking CAN interface: {e}")

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    print(f"Leader arm (/dev/ttyUSB0): {'✓ OK' if leader_ok else '❌ FAILED'}")
    print(f"\nIf motors are not found:")
    print(f"  1. Check if motors are powered on")
    print(f"  2. Check USB cable connections")
    print(f"  3. Try: sudo chmod 777 /dev/ttyUSB0")
    print(f"  4. Check baud rate settings on motors")

if __name__ == "__main__":
    main()
