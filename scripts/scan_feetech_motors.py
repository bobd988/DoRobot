#!/usr/bin/env python3
"""Scan for Feetech motors with multiple baud rates"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'operating_platform', 'robot', 'components', 'arm_normal_so101_v1'))

def scan_motors(port, baudrates):
    """Scan for motors at different baud rates"""
    import scservo_sdk as scs

    print(f"\n{'='*60}")
    print(f"Scanning {port} for Feetech motors")
    print(f"{'='*60}\n")

    for baudrate in baudrates:
        print(f"Trying baud rate: {baudrate}...")

        port_handler = scs.PortHandler(port)
        packet_handler = scs.PacketHandler(0)  # Protocol 0

        try:
            if not port_handler.openPort():
                print(f"  ❌ Failed to open port")
                continue

            if not port_handler.setBaudRate(baudrate):
                print(f"  ❌ Failed to set baud rate")
                port_handler.closePort()
                continue

            print(f"  ✓ Port opened at {baudrate} baud")

            # Scan for motors
            found = []
            for motor_id in range(1, 20):
                # Try to read model number (address 3, length 2)
                model_number, result, error = packet_handler.read2ByteTxRx(
                    port_handler, motor_id, 3
                )

                if result == scs.COMM_SUCCESS:
                    found.append((motor_id, model_number))
                    print(f"    ✓ Motor ID {motor_id}: Model {model_number}")

            port_handler.closePort()

            if found:
                print(f"\n  ✓✓✓ Found {len(found)} motor(s) at {baudrate} baud!")
                return baudrate, found
            else:
                print(f"  No motors found at this baud rate")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            try:
                port_handler.closePort()
            except:
                pass

    return None, []

def main():
    port = "/dev/ttyUSB0"

    # Common Feetech baud rates
    baudrates = [
        1000000,  # Default
        115200,
        57600,
        500000,
        250000,
        128000,
        76800,
        38400,
        19200,
        9600,
    ]

    print("Feetech Motor Scanner")
    print("="*60)
    print(f"Port: {port}")
    print(f"Testing {len(baudrates)} baud rates...")

    baudrate, motors = scan_motors(port, baudrates)

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    if motors:
        print(f"✓ SUCCESS!")
        print(f"  Baud rate: {baudrate}")
        print(f"  Found motors: {[m[0] for m in motors]}")
        print(f"\nMotor details:")
        for motor_id, model in motors:
            print(f"  ID {motor_id}: Model {model} (0x{model:04x})")
    else:
        print(f"❌ No motors found at any baud rate")
        print(f"\nTroubleshooting:")
        print(f"  1. Verify power is connected and ON")
        print(f"  2. Check USB cable connection")
        print(f"  3. Verify this is the correct USB port")
        print(f"  4. Check if motors are in a special mode")
        print(f"  5. Try: sudo chmod 777 {port}")

if __name__ == "__main__":
    main()
