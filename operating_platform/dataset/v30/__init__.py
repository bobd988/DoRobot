"""
LeRobot v3.0 dataset format utilities for DoRobot.

This module provides conversion tools for migrating datasets from v2.1 to v3.0.

Key changes in v3.0:
- Metadata stored in Parquet instead of JSONL
- Size-based file chunking instead of episode-based
- Video path structure: videos/{camera}/chunk-XXX/file-YYY.mp4
- Quantile statistics support (q01, q10, q50, q90, q99)
- Audio support preserved (DoRobot custom)
"""

from .convert_dataset_v21_to_v30 import convert_dataset

__all__ = ["convert_dataset"]
