from __future__ import annotations

import os
import socket
import time


def create_loopback_listener() -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    return listener


def apply_smoke_startup_delay() -> bool:
    value = str(os.environ.get("MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS", "") or "").strip()
    if not value:
        return True
    try:
        delay_seconds = min(max(int(value), 0), 5_000) / 1_000
    except ValueError:
        return False
    time.sleep(delay_seconds)
    return True
