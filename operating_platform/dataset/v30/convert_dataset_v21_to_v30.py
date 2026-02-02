#!/usr/bin/env python
"""
Convert DoRobot dataset from v2.1 to v3.0 format.

Key changes:
- episodes.jsonl -> meta/episodes/chunk-XXX/file-XXX.parquet
- tasks.jsonl -> meta/tasks.parquet
- Episode stats embedded in episode parquet
- Size-based file chunking instead of episode-based
- Video path restructuring: videos/chunk-XXX/{camera}/episode_YYY.mp4
  -> videos/{camera}/chunk-XXX/file-YYY.mp4
- Audio path restructuring (DoRobot custom): audio/chunk-XXX/{mic}/episode_YYY.wav
  -> audio/{mic}/chunk-XXX/file-YYY.wav
- Quantile statistics support

Usage:
    python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \\
        --repo-id=my-dataset \\
        --root=/path/to/dataset

    # With custom file size limits
    python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \\
        --repo-id=my-dataset \\
        --root=/path/to/dataset \\
        --data-file-size-mb=100 \\
        --video-file-size-mb=200
"""

import argparse
import json
import logging
import shutil
from pathlib import Path

import jsonlines
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datasets import Dataset
from tqdm import tqdm

from operating_platform.dataset.compute_stats import (
    DEFAULT_QUANTILES,
    aggregate_stats,
    compute_episode_stats,
)
from operating_platform.utils.dataset import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_DATA_FILE_SIZE_IN_MB,
    DEFAULT_VIDEO_FILE_SIZE_IN_MB,
    DEFAULT_DATA_PATH,
    DEFAULT_VIDEO_PATH,
    DEFAULT_AUDIO_PATH,
    DEFAULT_EPISODES_PATH,
    DEFAULT_TASKS_PATH,
    LEGACY_EPISODES_PATH,
    LEGACY_EPISODES_STATS_PATH,
    LEGACY_TASKS_PATH,
    flatten_dict,
    get_file_size_in_mb,
    load_info,
    load_json,
    update_chunk_file_indices,
    write_info,
    write_json,
    write_stats,
)
from operating_platform.utils.video import get_video_duration_in_s, concatenate_video_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

V21 = "v2.1"
V30 = "v3.0"


def load_legacy_jsonl(path: Path) -> list[dict]:
    """Load data from legacy JSONL file."""
    with jsonlines.open(path, "r") as reader:
        return list(reader)


def convert_tasks(root: Path, new_root: Path) -> pd.DataFrame:
    """Convert tasks.jsonl to tasks.parquet."""
    logger.info("Converting tasks...")

    tasks_path = root / LEGACY_TASKS_PATH
    if not tasks_path.exists():
        logger.warning(f"Tasks file not found: {tasks_path}")
        return pd.DataFrame(columns=["task_index"])

    tasks_data = load_legacy_jsonl(tasks_path)
    tasks_dict = {item["task"]: item["task_index"] for item in tasks_data}

    df_tasks = pd.DataFrame(
        {"task_index": list(tasks_dict.values())},
        index=list(tasks_dict.keys())
    )

    # Write to new location
    new_path = new_root / DEFAULT_TASKS_PATH
    new_path.parent.mkdir(parents=True, exist_ok=True)
    df_tasks.to_parquet(new_path)

    logger.info(f"Converted {len(df_tasks)} tasks to {new_path}")
    return df_tasks


def convert_data(
    root: Path,
    new_root: Path,
    info: dict,
    data_file_size_mb: int,
    chunks_size: int,
) -> list[dict]:
    """Convert episode parquet files with size-based chunking.

    Returns list of metadata dicts with data chunk/file indices for each episode.
    """
    logger.info("Converting data files...")

    legacy_data_path = info["data_path"]
    episodes_path = root / LEGACY_EPISODES_PATH
    episodes = load_legacy_jsonl(episodes_path)

    episode_metadata = []
    current_chunk_idx = 0
    current_file_idx = 0
    current_file_frames = 0
    current_file_size_mb = 0.0
    writer = None
    current_path = None

    for ep in tqdm(episodes, desc="Converting data"):
        ep_index = ep["episode_index"]

        # Load legacy episode data
        legacy_ep_chunk = ep_index // info.get("chunks_size", 10000)
        legacy_path = root / legacy_data_path.format(
            chunk_index=legacy_ep_chunk,
            episode_chunk=legacy_ep_chunk,
            episode_index=ep_index
        )

        if not legacy_path.exists():
            logger.warning(f"Episode data file not found: {legacy_path}")
            continue

        ep_dataset = Dataset.from_parquet(str(legacy_path))
        ep_size_mb = ep_dataset.data.nbytes / (1024 ** 2)

        # Check if we need a new file
        if writer is not None and (current_file_size_mb + ep_size_mb >= data_file_size_mb):
            writer.close()
            writer = None
            current_chunk_idx, current_file_idx = update_chunk_file_indices(
                current_chunk_idx, current_file_idx, chunks_size
            )
            current_file_frames = 0
            current_file_size_mb = 0.0

        # Create new file if needed
        if writer is None:
            current_path = new_root / DEFAULT_DATA_PATH.format(
                chunk_index=current_chunk_idx,
                file_index=current_file_idx
            )
            current_path.parent.mkdir(parents=True, exist_ok=True)
            table = ep_dataset.with_format("arrow")[:]
            writer = pq.ParquetWriter(current_path, schema=table.schema, compression="snappy")

        # Write episode data
        table = ep_dataset.with_format("arrow")[:]
        writer.write_table(table)

        # Track metadata
        ep_metadata = {
            "episode_index": ep_index,
            "data/chunk_index": current_chunk_idx,
            "data/file_index": current_file_idx,
            "dataset_from_index": current_file_frames,
            "dataset_to_index": current_file_frames + len(ep_dataset),
        }
        episode_metadata.append(ep_metadata)

        current_file_frames += len(ep_dataset)
        current_file_size_mb += ep_size_mb

    if writer is not None:
        writer.close()

    logger.info(f"Converted {len(episode_metadata)} episodes to new data format")
    return episode_metadata


def convert_videos(
    root: Path,
    new_root: Path,
    info: dict,
    video_file_size_mb: int,
    chunks_size: int,
) -> list[dict]:
    """Restructure video files with new path and size-based chunking.

    Returns list of metadata dicts with video chunk/file indices for each episode.
    """
    if info.get("video_path") is None:
        logger.info("No video path in dataset, skipping video conversion")
        return []

    logger.info("Converting video files...")

    legacy_video_path = info["video_path"]
    episodes_path = root / LEGACY_EPISODES_PATH
    episodes = load_legacy_jsonl(episodes_path)

    # Get video keys from features
    video_keys = [key for key, ft in info["features"].items() if ft["dtype"] == "video"]

    if not video_keys:
        logger.info("No video features found, skipping video conversion")
        return []

    video_metadata = []

    for vid_key in video_keys:
        logger.info(f"Converting videos for key: {vid_key}")

        current_chunk_idx = 0
        current_file_idx = 0
        current_file_size_mb = 0.0
        current_duration_s = 0.0
        pending_videos = []
        current_output_path = None

        for ep in tqdm(episodes, desc=f"Converting {vid_key}"):
            ep_index = ep["episode_index"]

            # Load legacy video
            legacy_ep_chunk = ep_index // info.get("chunks_size", 10000)
            legacy_path = root / legacy_video_path.format(
                episode_chunk=legacy_ep_chunk,
                video_key=vid_key,
                episode_index=ep_index
            )

            if not legacy_path.exists():
                logger.warning(f"Video file not found: {legacy_path}")
                continue

            ep_size_mb = get_file_size_in_mb(legacy_path)
            ep_duration_s = get_video_duration_in_s(legacy_path)

            # Check if we need a new file
            if current_file_size_mb + ep_size_mb >= video_file_size_mb and pending_videos:
                # Concatenate pending videos and write
                current_output_path = new_root / DEFAULT_VIDEO_PATH.format(
                    video_key=vid_key,
                    chunk_index=current_chunk_idx,
                    file_index=current_file_idx
                )
                current_output_path.parent.mkdir(parents=True, exist_ok=True)

                if len(pending_videos) == 1:
                    shutil.copy(str(pending_videos[0]["path"]), str(current_output_path))
                else:
                    concatenate_video_files(
                        [v["path"] for v in pending_videos],
                        current_output_path
                    )

                # Move to next file
                current_chunk_idx, current_file_idx = update_chunk_file_indices(
                    current_chunk_idx, current_file_idx, chunks_size
                )
                pending_videos = []
                current_file_size_mb = 0.0
                current_duration_s = 0.0

            # Track this episode's video metadata
            ep_video_metadata = {
                f"videos/{vid_key}/chunk_index": current_chunk_idx,
                f"videos/{vid_key}/file_index": current_file_idx,
                f"videos/{vid_key}/from_timestamp": current_duration_s,
                f"videos/{vid_key}/to_timestamp": current_duration_s + ep_duration_s,
            }

            # Find or create metadata entry for this episode
            found = False
            for vm in video_metadata:
                if vm.get("episode_index") == ep_index:
                    vm.update(ep_video_metadata)
                    found = True
                    break
            if not found:
                video_metadata.append({"episode_index": ep_index, **ep_video_metadata})

            pending_videos.append({"path": legacy_path, "duration": ep_duration_s})
            current_file_size_mb += ep_size_mb
            current_duration_s += ep_duration_s

        # Write remaining pending videos
        if pending_videos:
            current_output_path = new_root / DEFAULT_VIDEO_PATH.format(
                video_key=vid_key,
                chunk_index=current_chunk_idx,
                file_index=current_file_idx
            )
            current_output_path.parent.mkdir(parents=True, exist_ok=True)

            if len(pending_videos) == 1:
                shutil.copy(str(pending_videos[0]["path"]), str(current_output_path))
            else:
                concatenate_video_files(
                    [v["path"] for v in pending_videos],
                    current_output_path
                )

    logger.info(f"Converted videos for {len(episodes)} episodes")
    return video_metadata


def convert_audio(
    root: Path,
    new_root: Path,
    info: dict,
    chunks_size: int,
) -> list[dict]:
    """Convert audio files to new path structure (DoRobot custom).

    Audio files are copied without concatenation (unlike videos).
    """
    if info.get("audio_path") is None:
        logger.info("No audio path in dataset, skipping audio conversion")
        return []

    logger.info("Converting audio files...")

    legacy_audio_path = info["audio_path"]
    episodes_path = root / LEGACY_EPISODES_PATH
    episodes = load_legacy_jsonl(episodes_path)

    # Get audio keys from features
    audio_keys = [key for key, ft in info["features"].items() if ft["dtype"] == "audio"]

    if not audio_keys:
        logger.info("No audio features found, skipping audio conversion")
        return []

    audio_metadata = []

    for aud_key in audio_keys:
        logger.info(f"Converting audio for key: {aud_key}")

        # For audio, we use simple 1:1 mapping (one file per episode)
        for ep in tqdm(episodes, desc=f"Converting {aud_key}"):
            ep_index = ep["episode_index"]

            # Load legacy audio
            legacy_ep_chunk = ep_index // info.get("chunks_size", 10000)
            legacy_path = root / legacy_audio_path.format(
                episode_chunk=legacy_ep_chunk,
                audio_key=aud_key,
                episode_index=ep_index
            )

            if not legacy_path.exists():
                logger.warning(f"Audio file not found: {legacy_path}")
                continue

            # New path structure
            chunk_idx = ep_index // chunks_size
            file_idx = ep_index % chunks_size

            new_path = new_root / DEFAULT_AUDIO_PATH.format(
                audio_key=aud_key,
                chunk_index=chunk_idx,
                file_index=file_idx
            )
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(legacy_path), str(new_path))

            # Track metadata
            ep_audio_metadata = {
                f"audio/{aud_key}/chunk_index": chunk_idx,
                f"audio/{aud_key}/file_index": file_idx,
            }

            # Find or create metadata entry for this episode
            found = False
            for am in audio_metadata:
                if am.get("episode_index") == ep_index:
                    am.update(ep_audio_metadata)
                    found = True
                    break
            if not found:
                audio_metadata.append({"episode_index": ep_index, **ep_audio_metadata})

    logger.info(f"Converted audio for {len(episodes)} episodes")
    return audio_metadata


def convert_episodes_metadata(
    root: Path,
    new_root: Path,
    data_metadata: list[dict],
    video_metadata: list[dict],
    audio_metadata: list[dict],
) -> None:
    """Convert episodes.jsonl + episodes_stats.jsonl to parquet with embedded stats."""
    logger.info("Converting episode metadata...")

    episodes_path = root / LEGACY_EPISODES_PATH
    episodes = load_legacy_jsonl(episodes_path)

    stats_path = root / LEGACY_EPISODES_STATS_PATH
    if stats_path.exists():
        episodes_stats = load_legacy_jsonl(stats_path)
        stats_by_ep = {item["episode_index"]: item["stats"] for item in episodes_stats}
    else:
        stats_by_ep = {}

    # Build combined episode records
    combined_episodes = []
    for ep in episodes:
        ep_index = ep["episode_index"]

        # Handle both v2.1 formats: "task_index" (single task) or "tasks" (multi-task)
        tasks = ep.get("tasks", [ep.get("task_index", 0)])
        if isinstance(tasks, int):
            tasks = [tasks]

        record = {
            "episode_index": ep_index,
            "tasks": tasks,
            "length": ep["length"],
        }

        # Add data metadata
        for dm in data_metadata:
            if dm.get("episode_index") == ep_index:
                record.update({k: v for k, v in dm.items() if k != "episode_index"})
                break

        # Add video metadata
        for vm in video_metadata:
            if vm.get("episode_index") == ep_index:
                record.update({k: v for k, v in vm.items() if k != "episode_index"})
                break

        # Add audio metadata
        for am in audio_metadata:
            if am.get("episode_index") == ep_index:
                record.update({k: v for k, v in am.items() if k != "episode_index"})
                break

        # Add flattened stats
        if ep_index in stats_by_ep:
            flattened_stats = flatten_dict({"stats": stats_by_ep[ep_index]})
            # Convert numpy arrays to lists
            for key, value in flattened_stats.items():
                if isinstance(value, np.ndarray):
                    flattened_stats[key] = value.tolist()
            record.update(flattened_stats)

        combined_episodes.append(record)

    # Convert to Dataset and write to parquet
    # Note: We write all episodes to a single file for simplicity in conversion
    # Real datasets would use the buffering system for incremental writes
    episodes_dataset = Dataset.from_list(combined_episodes)

    output_path = new_root / DEFAULT_EPISODES_PATH.format(chunk_index=0, file_index=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    episodes_dataset.to_parquet(output_path)

    logger.info(f"Converted {len(combined_episodes)} episodes to {output_path}")


def convert_info(
    root: Path,
    new_root: Path,
    data_file_size_mb: int,
    video_file_size_mb: int,
    chunks_size: int,
) -> dict:
    """Update info.json for v3.0."""
    logger.info("Converting info.json...")

    info = load_info(root)

    # Update version
    info["codebase_version"] = V30

    # Remove deprecated fields
    info.pop("total_chunks", None)
    info.pop("total_videos", None)

    # Add new v3.0 fields
    info["chunks_size"] = chunks_size
    info["data_files_size_in_mb"] = data_file_size_mb
    info["video_files_size_in_mb"] = video_file_size_mb

    # Update path templates
    info["data_path"] = DEFAULT_DATA_PATH
    if info.get("video_path"):
        info["video_path"] = DEFAULT_VIDEO_PATH
    if info.get("audio_path"):
        info["audio_path"] = DEFAULT_AUDIO_PATH

    # Write updated info
    write_info(info, new_root)

    logger.info(f"Updated info.json with codebase_version={V30}")
    return info


def convert_dataset(
    repo_id: str,
    root: Path,
    output_root: Path | None = None,
    data_file_size_mb: int = DEFAULT_DATA_FILE_SIZE_IN_MB,
    video_file_size_mb: int = DEFAULT_VIDEO_FILE_SIZE_IN_MB,
    chunks_size: int = DEFAULT_CHUNK_SIZE,
    in_place: bool = False,
) -> None:
    """Main conversion function.

    Args:
        repo_id: Dataset repository ID
        root: Path to the v2.1 dataset
        output_root: Path for converted dataset (default: root + "_v30")
        data_file_size_mb: Max size per data file in MB
        video_file_size_mb: Max size per video file in MB
        chunks_size: Max files per chunk directory
        in_place: If True, convert in place (backup original)
    """
    root = Path(root)
    if output_root is not None:
        output_root = Path(output_root)

    if not root.exists():
        raise FileNotFoundError(f"Dataset not found at {root}")

    # Load and validate existing info
    info = load_info(root)
    current_version = info.get("codebase_version", "v2.1")

    if current_version == V30:
        logger.info(f"Dataset is already in v3.0 format: {root}")
        return

    if current_version < "v2.0":
        raise ValueError(f"Cannot convert from {current_version}. Please convert to v2.1 first.")

    logger.info(f"Converting dataset from {current_version} to {V30}")
    logger.info(f"Source: {root}")

    # Determine output directory
    if in_place:
        # Backup original
        backup_root = root.parent / f"{root.name}_backup_v21"
        if backup_root.exists():
            shutil.rmtree(backup_root)
        shutil.copytree(root, backup_root)
        new_root = root
        logger.info(f"Backup created at: {backup_root}")
    else:
        new_root = output_root or (root.parent / f"{root.name}_v30")
        if new_root.exists():
            shutil.rmtree(new_root)
        new_root.mkdir(parents=True)

    logger.info(f"Output: {new_root}")

    # Convert each component
    convert_tasks(root, new_root)

    data_metadata = convert_data(
        root, new_root, info, data_file_size_mb, chunks_size
    )

    video_metadata = convert_videos(
        root, new_root, info, video_file_size_mb, chunks_size
    )

    audio_metadata = convert_audio(
        root, new_root, info, chunks_size
    )

    convert_episodes_metadata(
        root, new_root, data_metadata, video_metadata, audio_metadata
    )

    new_info = convert_info(
        root, new_root, data_file_size_mb, video_file_size_mb, chunks_size
    )

    # Copy stats.json if exists
    stats_path = root / "meta/stats.json"
    if stats_path.exists():
        shutil.copy(stats_path, new_root / "meta/stats.json")

    logger.info("=" * 60)
    logger.info("Conversion complete!")
    logger.info(f"Converted dataset: {new_root}")
    logger.info(f"New version: {V30}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Convert DoRobot dataset from v2.1 to v3.0 format"
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        required=True,
        help="Dataset repository ID"
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Path to the v2.1 dataset"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for converted dataset (default: root_v30)"
    )
    parser.add_argument(
        "--data-file-size-mb",
        type=int,
        default=DEFAULT_DATA_FILE_SIZE_IN_MB,
        help=f"Max size per data file in MB (default: {DEFAULT_DATA_FILE_SIZE_IN_MB})"
    )
    parser.add_argument(
        "--video-file-size-mb",
        type=int,
        default=DEFAULT_VIDEO_FILE_SIZE_IN_MB,
        help=f"Max size per video file in MB (default: {DEFAULT_VIDEO_FILE_SIZE_IN_MB})"
    )
    parser.add_argument(
        "--chunks-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Max files per chunk directory (default: {DEFAULT_CHUNK_SIZE})"
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Convert in place (creates backup)"
    )

    args = parser.parse_args()

    convert_dataset(
        repo_id=args.repo_id,
        root=args.root,
        output_root=args.output,
        data_file_size_mb=args.data_file_size_mb,
        video_file_size_mb=args.video_file_size_mb,
        chunks_size=args.chunks_size,
        in_place=args.in_place,
    )


if __name__ == "__main__":
    main()
