#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import queue
import threading
import ssl
import traceback
import time

import websockets


try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


FLUSH_LOG_EVERY_SEC = float(os.environ.get("VR_FLUSH_LOG_EVERY_SEC", "0"))  # 0 = never
_last_flush_log = 0.0
_flush_total = 0

HOST = os.environ.get("VR_WS_HOST", "0.0.0.0")
PORT = int(os.environ.get("VR_WS_PORT", "8442"))

PRINT_FIRST_N = int(os.environ.get("VR_PRINT_FIRST_N", "1"))
MAX_QUEUE = int(os.environ.get("VR_MAX_QUEUE", "500"))

# 证书：和 8443 UI 用同一套
BASE = os.environ.get("TELEGRIP_ROOT", "/home/demo/synk/lerobot-main/telegrip-main")
CERT = os.environ.get("TELEGRIP_CERT", f"{BASE}/cert.pem")
KEY  = os.environ.get("TELEGRIP_KEY",  f"{BASE}/key.pem")


class WsServer:
    def __init__(self, out_q: "queue.Queue[bytes]"):
        self.out_q = out_q
        self.printed = 0

    async def handler(self, websocket):
        peer = websocket.remote_address
        print(f"[vr_ws_in] client connected: {peer}", flush=True)
        try:
            async for msg in websocket:
                raw = msg.encode("utf-8") if isinstance(msg, str) else bytes(msg)

                if self.printed < PRINT_FIRST_N:
                    # Try to parse and show grip status
                    try:
                        import json
                        data = json.loads(raw.decode('utf-8'))
                        lc = data.get('leftController', {})
                        grip = lc.get('gripActive', 'N/A')
                        trigger = lc.get('trigger', 'N/A')
                        print(f"[vr_ws_in] sample #{self.printed+1}: gripActive={grip}, trigger={trigger}, len={len(raw)}", flush=True)
                        print(f"[vr_ws_in] sample head={raw[:240]!r}", flush=True)
                    except:
                        print(f"[vr_ws_in] sample head={raw[:240]!r} len={len(raw)}", flush=True)
                    self.printed += 1

                try:
                    self.out_q.put_nowait(raw)
                except queue.Full:
                    # 队列满丢最新
                    pass
        except Exception as e:
            print(f"[vr_ws_in] client error: {peer} err={e}", flush=True)
        finally:
            print(f"[vr_ws_in] client disconnected: {peer}", flush=True)

    async def run(self):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(CERT, KEY)

        print(f"[vr_ws_in] listening on wss://{HOST}:{PORT}", flush=True)
        async with websockets.serve(
            self.handler,
            HOST,
            PORT,
            max_size=2**20,
            ssl=ssl_ctx,
        ):
            await asyncio.Future()  # run forever


def start_ws_thread(out_q: "queue.Queue[bytes]"):
    loop = asyncio.new_event_loop()
    server = WsServer(out_q)

    def _runner():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.run())
        except Exception:
            print("[vr_ws_in] WS server crashed:\n" + traceback.format_exc(), flush=True)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return t, loop


def main():
    global _last_flush_log, _flush_total  # ✅ 关键：声明使用模块级变量

    node = Node()

    out_q: "queue.Queue[bytes]" = queue.Queue(maxsize=MAX_QUEUE)
    _, loop = start_ws_thread(out_q)

    print("[vr_ws_in] waiting for VR client connection...", flush=True)
    print("[vr_ws_in] NOTE: must connect tick -> vr_ws_in in dataflow.yml", flush=True)

    try:
        for event in node:
            et = event.get("type")
            eid = event.get("id")

            if et == "STOP":
                break

            # 只在 tick 时把队列吐给 dora（避免线程里调用 send_output）
            if et == "INPUT" and eid == "tick":
                n = 0
                while True:
                    try:
                        raw = out_q.get_nowait()
                    except queue.Empty:
                        break
                    node.send_output("vr_event", raw, event.get("metadata", {}) or {})
                    n += 1

                if n > 0:
                    _flush_total += n

                if FLUSH_LOG_EVERY_SEC > 0:
                    now = time.time()
                    if now - _last_flush_log >= FLUSH_LOG_EVERY_SEC:
                        if _flush_total > 0:
                            print(f"[vr_ws_in] flushed {_flush_total} msg(s) in last {FLUSH_LOG_EVERY_SEC:.0f}s", flush=True)
                        _flush_total = 0
                        _last_flush_log = now

    finally:
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)


if __name__ == "__main__":
    main()
