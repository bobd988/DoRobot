import packaging.version

V2_MESSAGE = """
The dataset you requested ({repo_id}) is in {version} format.

We introduced a new format since v2.0 which is not backward compatible with v1.x.
Please, use our conversion script. Modify the following command with your own task description:
```
python lerobot/common/datasets/v2/convert_dataset_v1_to_v2.py \\
    --repo-id {repo_id} \\
    --single-task "TASK DESCRIPTION."  # <---- /!\\ Replace TASK DESCRIPTION /!\\
```

A few examples to replace TASK DESCRIPTION: "Pick up the blue cube and place it into the bin.", "Insert the
peg into the socket.", "Slide open the ziploc bag.", "Take the elevator to the 1st floor.", "Open the top
cabinet, store the pot inside it then close the cabinet.", "Push the T-shaped block onto the T-shaped
target.", "Grab the spray paint on the shelf and place it in the bin on top of the robot dog.", "Fold the
sweatshirt.", ...

If you encounter a problem, contact LeRobot maintainers on [Discord](https://discord.com/invite/s3KuuzsPFb)
or open an [issue on GitHub](https://github.com/huggingface/lerobot/issues/new/choose).
"""

V21_MESSAGE = """
The dataset you requested ({repo_id}) is in {version} format.
While current version of LeRobot is backward-compatible with it, the version of your dataset still uses global
stats instead of per-episode stats. Update your dataset stats to the new format using this command:
```
python lerobot/common/datasets/v21/convert_dataset_v20_to_v21.py --repo-id={repo_id}
```

If you encounter a problem, contact LeRobot maintainers on [Discord](https://discord.com/invite/s3KuuzsPFb)
or open an [issue on GitHub](https://github.com/huggingface/lerobot/issues/new/choose).
"""

V30_MESSAGE = """
The dataset you requested ({repo_id}) is in {version} format.

LeRobot v3.0 introduced a new format with significant changes:
- Metadata stored in Parquet instead of JSONL
- Size-based file chunking instead of episode-based
- Video path structure changed to videos/{{camera}}/chunk-XXX/file-YYY.mp4
- Quantile statistics support (q01, q10, q50, q90, q99)

Please convert your dataset using:
```
python -m operating_platform.dataset.v30.convert_dataset_v21_to_v30 \\
    --repo-id={repo_id} \\
    --root=/path/to/dataset
```

This is a one-time migration that will update your dataset to v3.0 format.
"""

FUTURE_MESSAGE = """
The dataset you requested ({repo_id}) is only available in {version} format.
As we cannot ensure forward compatibility with it, please update your current version of lerobot.
"""


class CompatibilityError(Exception): ...


class BackwardCompatibilityError(CompatibilityError):
    def __init__(self, repo_id: str, version: packaging.version.Version):
        # Select appropriate message based on version
        if version.major < 2:
            message = V2_MESSAGE.format(repo_id=repo_id, version=version)
        elif version < packaging.version.parse("v3.0"):
            message = V30_MESSAGE.format(repo_id=repo_id, version=version)
        else:
            message = V2_MESSAGE.format(repo_id=repo_id, version=version)
        super().__init__(message)


class ForwardCompatibilityError(CompatibilityError):
    def __init__(self, repo_id: str, version: packaging.version.Version):
        message = FUTURE_MESSAGE.format(repo_id=repo_id, version=version)
        super().__init__(message)
