#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import ssl
import sys
import signal
import socket
import traceback
import threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    from dora import Node
except Exception:
    from dora import DoraNode as Node


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def build_server():
    host = os.environ.get("TELEGRIP_UI_HOST", "0.0.0.0")
    port = int(os.environ.get("TELEGRIP_UI_PORT", "8443"))

    base = Path(os.environ.get("TELEGRIP_ROOT", "/home/demo/synk/lerobot-main/telegrip-main")).resolve()
    ui_dir = Path(os.environ.get("TELEGRIP_UI_DIR", str(base / "web-ui"))).resolve()
    cert = Path(os.environ.get("TELEGRIP_CERT", str(base / "cert.pem"))).resolve()
    key  = Path(os.environ.get("TELEGRIP_KEY",  str(base / "key.pem"))).resolve()

    print(f"[telegrip_https_ui] ui_dir={ui_dir}", flush=True)
    print(f"[telegrip_https_ui] cert={cert}", flush=True)
    print(f"[telegrip_https_ui] key ={key}", flush=True)

    if not ui_dir.exists():
        raise FileNotFoundError(f"web ui dir not found: {ui_dir}")
    if not cert.exists():
        raise FileNotFoundError(f"cert not found: {cert}")
    if not key.exists():
        raise FileNotFoundError(f"key not found: {key}")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ui_dir), **kwargs)
        def log_message(self, format, *args):
            return  # 静音

    httpd = ThreadingHTTPServer((host, port), Handler)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(cert), keyfile=str(key))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    show_ip = get_local_ip() if host == "0.0.0.0" else host
    print(f"[telegrip_https_ui] ✅ serving https://{show_ip}:{port}", flush=True)

    return httpd


def main():
    node = Node()  # ✅ 关键：让 Dora 看到这个进程是一个 node

    httpd = build_server()
    stop_flag = {"stop": False}

    # 让 server 在后台线程跑，主线程处理 dora event
    def run_server():
        try:
            httpd.serve_forever(poll_interval=0.5)
        except Exception as e:
            print(f"[telegrip_https_ui] server thread error: {e}", flush=True)

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    def _sig(*_):
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    try:
        for event in node:
            if stop_flag["stop"]:
                break
            if event.get("type") == "STOP":
                break
            # 可选：如果你把 tick 连进来，这里会收到 INPUT tick，但不需要处理
    finally:
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        print("[telegrip_https_ui] stopped", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[telegrip_https_ui] FATAL:\n" + traceback.format_exc(), flush=True)
        sys.exit(1)
