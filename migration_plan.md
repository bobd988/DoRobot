# DoRobot LeRobot v2.1 to v3.0 Migration Plan

## Executive Summary

This document outlines the migration plan to upgrade DoRobot from LeRobot dataset format **v2.1** to **v3.0**. The v3.0 format introduces significant architectural changes that improve scalability for large datasets while maintaining backward compatibility through a conversion tool.

**Target Branch:** `upgrade_4.3`
**Source Reference:** `/home/demo/Public/lerobot` (LeRobot v3.0)
**Target Repository:** `/home/demo/Public/DoRobot`

---

## 1. Key Changes in LeRobot v3.0

### 1.1 Breaking Changes Summary

| Aspect | v2.1 (Current) | v3.0 (Target) |
|--------|----------------|---------------|
| **Codebase Version** | `LEROBOT_DATASET_VERSION = "v2.1"` | `LEROBOT_DATASET_VERSION = "v3.0"` |
| **Metadata Format** | JSONL files | Parquet files (columnar) |
| **Episodes Storage** | `meta/episodes.jsonl` | `meta/episodes/chunk-XXX/file-YYY.parquet` |
| **Tasks Storage** | `meta/tasks.jsonl` | `meta/tasks.parquet` |
| **Stats Storage** | `meta/episodes_stats.jsonl` | Embedded in episode parquet |
| **File Chunking** | Episode-based (10K episodes/chunk) | Size-based (100MB data, 200MB video) |
| **Data Path** | `data/chunk-{ep_chunk}/episode_{ep_idx}.parquet` | `data/chunk-{chunk}/file-{file}.parquet` |
| **Video Path** | `videos/chunk-{chunk}/{camera}/episode_{idx}.mp4` | `videos/{camera}/chunk-{chunk}/file-{file}.mp4` |
| **Statistics** | min, max, mean, std, count | + quantiles (q01, q10, q50, q90, q99) |
| **Backward Compat** | Supports v2.0 datasets | No v2.1 support (requires conversion) |

### 1.2 Benefits of v3.0

1. **Improved Scalability**: Size-based file chunking prevents extremely large files
2. **Better I/O Performance**: Parquet columnar format for faster metadata queries
3. **Richer Statistics**: Quantile support for better normalization options
4. **Efficient Metadata Writes**: Buffered writes reduce I/O operations during recording

---

## 2. DoRobot Custom Features to Preserve

The following DoRobot-specific features MUST be preserved during migration:

| Feature | Location | Notes |
|---------|----------|-------|
| **Audio Recording** | `dorobot_dataset.py`, `audio_writer.py` | v3.0 removed audio; DoRobot keeps it |
| **Thread-safe Metadata** | `_meta_lock` in `DoRobotDatasetMetadata` | For async episode saving |
| **Async Episode Saver** | `async_episode_saver.py` | Non-blocking saves during recording |
| **Ascend NPU Encoding** | `utils/video.py` | Hardware video encoding support |
| **DoRobot Version** | `DOROBOT_DATASET_VERSION` | Independent DoRobot versioning |

---

## 3. Files to Modify

### 3.1 `operating_platform/dataset/dorobot_dataset.py`

**Changes Required:**

1. **Update version constants** (lines 75-76):
   ```python
   LEROBOT_DATASET_VERSION = "v3.0"  # Was "v2.1"
   DOROBOT_DATASET_VERSION = "v1.1"  # Bump from "v1.0"
   ```

2. **Add imports**:
   ```python
   import pyarrow as pa
   import pyarrow.parquet as pq
   import pandas as pd
   ```

3. **Update `DoRobotDatasetMetadata.__init__`**:
   ```python
   def __init__(
       self,
       repo_id: str,
       root: str | Path | None = None,
       revision: str | None = None,
       force_cache_sync: bool = False,
       metadata_buffer_size: int = 10,  # NEW
   ):
       # ... existing code ...

       # NEW: v3.0 metadata buffering
       self.writer = None
       self.latest_episode = None
       self.metadata_buffer: list[dict] = []
       self.metadata_buffer_size = metadata_buffer_size
   ```

4. **Add metadata buffer methods**:
   ```python
   def _flush_metadata_buffer(self) -> None:
       """Write buffered episode metadata to parquet."""
       if len(self.metadata_buffer) == 0:
           return
       # ... implementation ...

   def _close_writer(self) -> None:
       """Close parquet writer and flush remaining buffer."""
       self._flush_metadata_buffer()
       if self.writer:
           self.writer.close()
           self.writer = None

   def __del__(self):
       """Cleanup on destruction."""
       self._close_writer()
   ```

5. **Update path methods**:
   ```python
   def get_data_file_path(self, ep_index: int) -> Path:
       """Get data file path using chunk/file indices."""
       ep = self.episodes[ep_index]
       return Path(self.data_path.format(
           chunk_index=ep["data/chunk_index"],
           file_index=ep["data/file_index"]
       ))

   def get_video_file_path(self, ep_index: int, vid_key: str) -> Path:
       """Get video file path using new structure."""
       ep = self.episodes[ep_index]
       return Path(self.video_path.format(
           video_key=vid_key,
           chunk_index=ep[f"videos/{vid_key}/chunk_index"],
           file_index=ep[f"videos/{vid_key}/file_index"]
       ))

   # Preserve audio support
   def get_audio_file_path(self, ep_index: int, aud_key: str) -> Path:
       """Get audio file path (DoRobot custom)."""
       ep = self.episodes[ep_index]
       return Path(self.audio_path.format(
           audio_key=aud_key,
           chunk_index=ep.get(f"audio/{aud_key}/chunk_index", 0),
           file_index=ep.get(f"audio/{aud_key}/file_index", 0)
       ))
   ```

6. **Update `save_episode` method** to accept episode_metadata and write to Parquet

7. **Add `finalize()` method** to DoRobotDataset class

### 3.2 `operating_platform/utils/dataset.py`

**Changes Required:**

1. **Add new constants**:
   ```python
   # v3.0 chunking constants
   DEFAULT_CHUNK_SIZE = 1000  # Files per chunk directory
   DEFAULT_DATA_FILE_SIZE_IN_MB = 100
   DEFAULT_VIDEO_FILE_SIZE_IN_MB = 200

   # v3.0 path patterns
   CHUNK_FILE_PATTERN = "chunk-{chunk_index:03d}/file-{file_index:03d}"
   EPISODES_DIR = "meta/episodes"
   DEFAULT_EPISODES_PATH = EPISODES_DIR + "/" + CHUNK_FILE_PATTERN + ".parquet"
   DEFAULT_TASKS_PATH = "meta/tasks.parquet"
   DEFAULT_DATA_PATH = "data/" + CHUNK_FILE_PATTERN + ".parquet"
   DEFAULT_VIDEO_PATH = "videos/{video_key}/" + CHUNK_FILE_PATTERN + ".mp4"
   DEFAULT_AUDIO_PATH = "audio/{audio_key}/" + CHUNK_FILE_PATTERN + ".wav"  # DoRobot

   # Legacy paths (for conversion)
   LEGACY_EPISODES_PATH = "meta/episodes.jsonl"
   LEGACY_EPISODES_STATS_PATH = "meta/episodes_stats.jsonl"
   LEGACY_TASKS_PATH = "meta/tasks.jsonl"
   ```

2. **Add helper functions**:
   ```python
   def update_chunk_file_indices(
       chunk_idx: int, file_idx: int, chunks_size: int
   ) -> tuple[int, int]:
       """Move to next file/chunk when size limit reached."""
       if file_idx == chunks_size - 1:
           return chunk_idx + 1, 0
       return chunk_idx, file_idx + 1

   def get_file_size_in_mb(file_path: Path) -> float:
       """Get file size in megabytes."""
       return file_path.stat().st_size / (1024 ** 2)

   def load_nested_dataset(
       pq_dir: Path,
       features: datasets.Features | None = None,
       episodes: list[int] | None = None
   ) -> datasets.Dataset:
       """Load parquet files from nested chunk/file structure."""
       paths = sorted(pq_dir.glob("*/*.parquet"))
       if not paths:
           raise FileNotFoundError(f"No parquet files in {pq_dir}")

       if episodes is None:
           return datasets.Dataset.from_parquet(
               [str(p) for p in paths], features=features
           )

       import pyarrow.dataset as pa_ds
       arrow_dataset = pa_ds.dataset(paths, format="parquet")
       filter_expr = pa_ds.field("episode_index").isin(episodes)
       table = arrow_dataset.to_table(filter=filter_expr)
       return datasets.Dataset(table)

   def flatten_dict(nested: dict, sep: str = "/") -> dict:
       """Flatten nested dict: {'a': {'b': 1}} -> {'a/b': 1}"""
       result = {}
       for key, value in nested.items():
           if isinstance(value, dict):
               for subkey, subvalue in flatten_dict(value, sep).items():
                   result[f"{key}{sep}{subkey}"] = subvalue
           else:
               result[key] = value
       return result

   def unflatten_dict(flat: dict, sep: str = "/") -> dict:
       """Unflatten dict: {'a/b': 1} -> {'a': {'b': 1}}"""
       result = {}
       for key, value in flat.items():
           parts = key.split(sep)
           d = result
           for part in parts[:-1]:
               d = d.setdefault(part, {})
           d[parts[-1]] = value
       return result
   ```

3. **Update `load_episodes()`** to read from Parquet

4. **Update `load_tasks()`** to read from Parquet

5. **Update `create_empty_dataset_info()`**:
   ```python
   def create_empty_dataset_info(
       codebase_version: str,
       dorobot_dataset_version: str,
       fps: int,
       robot_type: str,
       features: dict,
       use_videos: bool,
       use_audios: bool,
       chunks_size: int = DEFAULT_CHUNK_SIZE,
       data_files_size_in_mb: int = DEFAULT_DATA_FILE_SIZE_IN_MB,
       video_files_size_in_mb: int = DEFAULT_VIDEO_FILE_SIZE_IN_MB,
   ) -> dict:
       return {
           "codebase_version": codebase_version,
           "dorobot_dataset_version": dorobot_dataset_version,
           "robot_type": robot_type,
           "total_episodes": 0,
           "total_frames": 0,
           "total_tasks": 0,
           "chunks_size": chunks_size,
           "data_files_size_in_mb": data_files_size_in_mb,
           "video_files_size_in_mb": video_files_size_in_mb,
           "fps": fps,
           "splits": {},
           "data_path": DEFAULT_DATA_PATH,
           "video_path": DEFAULT_VIDEO_PATH if use_videos else None,
           "audio_path": DEFAULT_AUDIO_PATH if use_audios else None,
           "features": features,
       }
   ```

### 3.3 `operating_platform/dataset/compute_stats.py`

**Changes Required:**

1. **Add quantile constants**:
   ```python
   DEFAULT_QUANTILES = [0.01, 0.10, 0.50, 0.90, 0.99]
   QUANTILE_KEYS = ["q01", "q10", "q50", "q90", "q99"]
   ```

2. **Add `RunningQuantileStats` class** (port from LeRobot v3.0):
   ```python
   class RunningQuantileStats:
       """Maintains running statistics including approximate quantiles."""

       def __init__(self, shape: tuple, num_bins: int = 10000):
           self.shape = shape
           self.num_bins = num_bins
           self.min = np.full(shape, np.inf)
           self.max = np.full(shape, -np.inf)
           self.sum = np.zeros(shape)
           self.sum_sq = np.zeros(shape)
           self.count = 0
           self.histograms = None
           self.bin_edges = None

       def update(self, batch: np.ndarray) -> None:
           """Update statistics with a new batch."""
           # ... implementation ...

       def get_stats(self) -> dict:
           """Get computed statistics including quantiles."""
           # ... implementation ...
   ```

3. **Update `get_feature_stats()`** to compute quantiles

4. **Update `compute_episode_stats()`** to return quantiles

5. **Update `aggregate_stats()`** to aggregate quantiles correctly

### 3.4 `operating_platform/utils/video.py`

**Add Functions:**

```python
def concatenate_video_files(
    input_paths: list[Path], output_path: Path
) -> None:
    """Concatenate multiple video files using ffmpeg concat demuxer."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for path in input_paths:
            f.write(f"file '{path}'\n")
        concat_file = f.name

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_suffix('.tmp.mp4')

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', str(temp_output)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(str(temp_output), str(output_path))
    finally:
        Path(concat_file).unlink(missing_ok=True)


def get_video_duration_in_s(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())
```

### 3.5 `operating_platform/dataset/backward_compatibility.py`

**Add v3.0 Message:**

```python
V30_MESSAGE = """
The dataset you requested ({repo_id}) is in {version} format.

LeRobot v3.0 introduced a new format that is not backward compatible with v2.1.
Please convert your dataset using:

    python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \\
        --repo-id={repo_id} \\
        --root=/path/to/dataset

For more information, see the migration guide.
"""
```

---

## 4. New Files to Create

### 4.1 `operating_platform/dataset/v30/__init__.py`

```python
"""
LeRobot v3.0 dataset format utilities.

This module provides conversion tools for migrating datasets from v2.1 to v3.0.
"""

from .convert_dataset_v21_to_v30 import convert_dataset

__all__ = ["convert_dataset"]
```

### 4.2 `operating_platform/dataset/v30/convert_dataset_v21_to_v30.py`

Full conversion script with the following functions:

- `load_legacy_jsonl(path)` - Read JSONL files
- `convert_tasks(root, new_root)` - Convert tasks.jsonl to tasks.parquet
- `convert_data(root, new_root, info, data_size_mb)` - Rechunk data files by size
- `convert_videos(root, new_root, info, video_size_mb)` - Restructure and concatenate videos
- `convert_audio(root, new_root, info)` - Migrate audio files (DoRobot custom)
- `convert_episodes_metadata(root, new_root, data_meta, video_meta, audio_meta)` - Create Parquet episodes
- `convert_info(root, new_root, data_size_mb, video_size_mb)` - Update info.json
- `convert_dataset(repo_id, root, **kwargs)` - Main entry point

**Usage:**
```bash
python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \
    --repo-id=my-dataset \
    --root=/path/to/v21/dataset \
    --data-file-size-mb=100 \
    --video-file-size-mb=200
```

---

## 5. Implementation Order

| Step | Task | File(s) | Dependencies |
|------|------|---------|--------------|
| 1 | Add new constants and helpers | `utils/dataset.py` | None |
| 2 | Add quantile statistics | `compute_stats.py` | None |
| 3 | Add video utilities | `utils/video.py` | None |
| 4 | Update DoRobotDatasetMetadata | `dorobot_dataset.py` | Steps 1-2 |
| 5 | Update DoRobotDataset | `dorobot_dataset.py` | Step 4 |
| 6 | Update backward compatibility | `backward_compatibility.py` | None |
| 7 | Create conversion script | `v30/convert_dataset_v21_to_v30.py` | Steps 1-3 |
| 8 | Test new dataset creation | - | Steps 1-5 |
| 9 | Test v2.1 to v3.0 conversion | - | Step 7 |

---

## 6. Reference Files from LeRobot v3.0

Copy/adapt implementation patterns from:

| LeRobot v3.0 File | Purpose |
|-------------------|---------|
| `src/lerobot/datasets/lerobot_dataset.py` | Metadata buffering (lines 84-200) |
| `src/lerobot/datasets/utils.py` | Chunking helpers, flatten/unflatten |
| `src/lerobot/datasets/compute_stats.py` | `RunningQuantileStats` class |
| `src/lerobot/datasets/v30/convert_dataset_v21_to_v30.py` | Conversion logic |
| `src/lerobot/datasets/video_utils.py` | Video concatenation |

---

## 7. Testing Plan

### 7.1 Unit Tests

Create new test files in `test/dataset/`:

- `test_dorobot_dataset_v30.py` - v3.0 format creation/loading
- `test_compute_stats_quantiles.py` - Quantile computation
- `test_size_based_chunking.py` - File size chunking logic
- `test_conversion_v21_to_v30.py` - Conversion script

### 7.2 Integration Tests

```bash
# Test new dataset creation
python -c "
from operating_platform.dataset.dorobot_dataset import DoRobotDataset
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    ds = DoRobotDataset.create(
        repo_id='test-v30',
        fps=30,
        root=tmp,
        features={
            'observation.state': {'dtype': 'float32', 'shape': (6,)},
            'action': {'dtype': 'float32', 'shape': (6,)},
        }
    )
    print(f'Created v3.0 dataset at {tmp}')
    print(f'Version: {ds.meta.info[\"codebase_version\"]}')
"
```

### 7.3 Conversion Test

```bash
# Convert existing v2.1 dataset
python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \
    --repo-id=test \
    --root=/path/to/existing/v21/dataset
```

---

## 8. Verification Checklist

After implementation, verify:

- [ ] `info.json` shows `codebase_version: "v3.0"`
- [ ] `info.json` contains `data_files_size_in_mb` and `video_files_size_in_mb`
- [ ] Episodes stored in `meta/episodes/chunk-XXX/file-YYY.parquet`
- [ ] Tasks stored in `meta/tasks.parquet`
- [ ] Data files respect 100MB size limit
- [ ] Video files follow `videos/{camera}/chunk-XXX/file-YYY.mp4` structure
- [ ] Audio files preserved (DoRobot custom) with new path structure
- [ ] Stats include quantiles (q01, q10, q50, q90, q99)
- [ ] Thread-safe async saves still work with `_meta_lock`
- [ ] NPU video encoding still functional
- [ ] Conversion script successfully migrates v2.1 datasets

---

## 9. Rollback Plan

If issues arise during migration:

1. **Git rollback**: `git checkout main` to return to v2.1
2. **Dataset compatibility**: v2.1 datasets remain usable with v2.1 code
3. **Conversion reversibility**: Original v2.1 datasets are not modified in-place by default

---

## 10. Post-Migration Tasks

1. Update documentation in `docs/`
2. Update `RELEASE.md` with v3.0 migration notes
3. Test with actual robot data collection
4. Verify NPU encoding workflow
5. Update CLAUDE.md with v3.0 notes

---

## Appendix: info.json Schema Comparison

### v2.1 Schema
```json
{
  "codebase_version": "v2.1",
  "dorobot_dataset_version": "v1.0",
  "robot_type": "so101",
  "total_episodes": 50,
  "total_frames": 5000,
  "total_tasks": 3,
  "total_videos": 150,
  "total_chunks": 1,
  "chunks_size": 10000,
  "fps": 30,
  "splits": {"train": "0:50"},
  "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
  "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
  "audio_path": "audio/chunk-{episode_chunk:03d}/{audio_key}/episode_{episode_index:06d}.wav",
  "features": {...}
}
```

### v3.0 Schema
```json
{
  "codebase_version": "v3.0",
  "dorobot_dataset_version": "v1.1",
  "robot_type": "so101",
  "total_episodes": 50,
  "total_frames": 5000,
  "total_tasks": 3,
  "chunks_size": 1000,
  "data_files_size_in_mb": 100,
  "video_files_size_in_mb": 200,
  "fps": 30,
  "splits": {"train": "0:50"},
  "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
  "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
  "audio_path": "audio/{audio_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.wav",
  "features": {...}
}
```

---

*Generated: 2026-02-02*
*Branch: upgrade_4.3*
*Target: LeRobot v3.0 compatibility*
