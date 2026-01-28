#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import Any, Optional

import pyarrow as pa

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


def extract_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    if isinstance(value, pa.Array):
        if len(value) == 0:
            return None
        if pa.types.is_uint8(value.type) or pa.types.is_int8(value.type):
            return bytes(value.to_pylist())

        scalar = value[0]
        item = scalar.as_py()
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


def main() -> None:
    node = Node()

    for event in node:
        et = event.get("type")
        eid = event.get("id")

        if et == "STOP":
            break
        if et != "INPUT":
            continue
        if eid == "tick":
            continue
        if eid != "arm_cmd":
            continue

        raw = extract_bytes(event.get("value"))
        if not raw:
            continue

        cmd = json.loads(raw.decode("utf-8"))
        # 你现在能看到 mux 产出的标准格式
        print("[robot_driver_stub] arm_cmd:", cmd, flush=True)


if __name__ == "__main__":
    main()
