from __future__ import annotations

import hmac
import json
import os
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PROTOCOL_VERSION = 1
SIDECAR_VERSION = "0.1.0-spike"


class SidecarServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token: str) -> None:
        super().__init__(("127.0.0.1", 0), SidecarRequestHandler)
        self.token = token


class SidecarRequestHandler(BaseHTTPRequestHandler):
    server: SidecarServer

    def do_GET(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"code": "unauthorized"})
            return
        if self.path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "state": "healthy",
                    "protocol": PROTOCOL_VERSION,
                    "version": SIDECAR_VERSION,
                    "capabilities": ["health", "lifecycle"],
                },
            )
            return
        if self.path == "/capabilities":
            self._json(
                HTTPStatus.OK,
                {"capabilities": ["health", "lifecycle"]},
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"code": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"code": "unauthorized"})
            return
        if self.path != "/shutdown":
            self._json(HTTPStatus.NOT_FOUND, {"code": "not_found"})
            return
        self._json(HTTPStatus.OK, {"state": "stopping"})
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, message_format: str, *args: Any) -> None:
        print(
            f"{self.address_string()} - {message_format % args}",
            file=sys.stderr,
            flush=True,
        )

    def _authorized(self) -> bool:
        authorization = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        return hmac.compare_digest(authorization, expected)

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def build_server(token: str) -> SidecarServer:
    if not token:
        raise ValueError("Sidecar token is required")
    return SidecarServer(token)


def _watch_parent_pipe(server: SidecarServer) -> None:
    try:
        stdin_fd = sys.stdin.fileno()
        while os.read(stdin_fd, 1):
            pass
    finally:
        server.shutdown()


def main() -> int:
    token = os.environ.get("MARA_DESKTOP_TOKEN", "")
    if not token:
        print("MARA_DESKTOP_TOKEN is required", file=sys.stderr)
        return 2

    server = build_server(token)

    def stop_server(_signum: int, _frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    threading.Thread(target=_watch_parent_pipe, args=(server,), daemon=True).start()

    host, port = server.server_address
    ready = {
        "type": "ready",
        "protocol": PROTOCOL_VERSION,
        "port": port,
        "pid": os.getpid(),
    }
    print(json.dumps(ready, separators=(",", ":")), flush=True)

    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
