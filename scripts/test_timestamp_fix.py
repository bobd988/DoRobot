#!/usr/bin/env python3
"""
Test script to verify that real timestamps are being used in recorded data.

This script checks if the timestamps in a newly recorded episode show
real time intervals (with natural variation) rather than ideal intervals
(perfect 0.0333s for 30fps).

Usage:
    python scripts/test_timestamp_fix.py <path_to_episode_parquet>

Example:
    python scripts/test_timestamp_fix.py ~/DoRobot/dataset/leader-follower-x5/data/chunk-000/episode_000000.parquet
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path


def check_timestamps(parquet_path: str):
    """Check if timestamps show real time intervals or ideal intervals."""

    path = Path(parquet_path)
    if not path.exists():
        print(f"Error: File not found: {parquet_path}")
        return False

    # Read parquet file
    df = pd.read_parquet(path)

    if 'timestamp' not in df.columns:
        print("Error: No 'timestamp' column found in parquet file")
        return False

    timestamps = df['timestamp'].values

    if len(timestamps) < 2:
        print("Error: Not enough timestamps to analyze")
        return False

    # Calculate frame intervals
    intervals = np.diff(timestamps)

    # Statistics
    mean_interval = np.mean(intervals)
    std_interval = np.std(intervals)
    min_interval = np.min(intervals)
    max_interval = np.max(intervals)

    # Expected interval for 30fps
    expected_interval = 1.0 / 30.0  # 0.0333s

    print("=" * 60)
    print("TIMESTAMP ANALYSIS")
    print("=" * 60)
    print(f"File: {parquet_path}")
    print(f"Total frames: {len(timestamps)}")
    print(f"Duration: {timestamps[-1]:.2f}s")
    print()
    print("Frame Intervals:")
    print(f"  Mean:     {mean_interval:.6f}s")
    print(f"  Std Dev:  {std_interval:.6f}s")
    print(f"  Min:      {min_interval:.6f}s")
    print(f"  Max:      {max_interval:.6f}s")
    print(f"  Expected: {expected_interval:.6f}s (30fps)")
    print()

    # Determine if using real timestamps or ideal timestamps
    # Real timestamps should have std dev > 0.001s
    # Ideal timestamps have std dev ~0.0s
    if std_interval < 0.0001:
        print("❌ USING IDEAL TIMESTAMPS (calculated from frame_index / fps)")
        print("   Video will play faster than actual operation speed")
        print()
        print("   This means the timestamp fix is NOT working.")
        print("   The system is still using calculated timestamps.")
        return False
    else:
        print("✅ USING REAL TIMESTAMPS (actual system time)")
        print("   Video playback speed will match actual operation speed")
        print()
        print("   The timestamp fix is working correctly!")
        return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_timestamp_fix.py <path_to_episode_parquet>")
        print()
        print("Example:")
        print("  python scripts/test_timestamp_fix.py ~/DoRobot/dataset/leader-follower-x5/data/chunk-000/episode_000000.parquet")
        sys.exit(1)

    parquet_path = sys.argv[1]
    success = check_timestamps(parquet_path)
    sys.exit(0 if success else 1)
