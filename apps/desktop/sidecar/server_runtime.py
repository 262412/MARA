from __future__ import annotations

import os
import socket
import sys
import time


def wait_for_parent_pipe(stdin_fd: int) -> None:
    if sys.platform != "win32":
        while os.read(stdin_fd, 1):
            pass
        return

    import ctypes
    import msvcrt
    from ctypes import wintypes

    # A pending synchronous pipe read can block native DLL initialization on
    # Windows. Read only available bytes, keeping the parent's borrowed FD open.
    peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
    peek.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    )
    peek.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(stdin_fd)
    available = wintypes.DWORD()
    while peek(handle, None, 0, None, ctypes.byref(available), None):
        if available.value:
            os.read(stdin_fd, min(available.value, 4096))
        else:
            time.sleep(0.05)
    error = ctypes.get_last_error()
    if error != 109:  # ERROR_BROKEN_PIPE means the parent closed its write end.
        raise ctypes.WinError(error)


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
