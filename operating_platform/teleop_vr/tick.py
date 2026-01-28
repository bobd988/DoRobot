#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


HZ = float(os.environ.get("TICK_HZ", "50"))  # 50Hz
DT = 1.0 / HZ


def main():
    node = Node()
    print(f"[tick] start {HZ} Hz", flush=True)

    i = 0
    next_t = time.time()

    while True:
        now = time.time()
        if now < next_t:
            time.sleep(min(0.002, next_t - now))
            continue

        next_t += DT
        i += 1

        # tick 内容随便，大家只用“事件到达”这一点
        node.send_output("tick", b"1", {})

        # 每秒打一次，确认它真的在跑
        # if i % int(HZ) == 0:
        #     print(f"[tick] alive i={i}", flush=True)


if __name__ == "__main__":
    main()
