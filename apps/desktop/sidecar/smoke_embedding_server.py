from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 1_048_576


def _embedding(value: str | list[int]) -> list[float]:
    canonical = value if isinstance(value, str) else json.dumps(value)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    values = [(value - 127.5) / 127.5 for value in digest[:16]]
    magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / magnitude for value in values]


def create_server(
    token: str,
    port: int = 0,
    *,
    failure_marker: Path | None = None,
    block_marker: Path | None = None,
    request_marker: Path | None = None,
) -> ThreadingHTTPServer:
    if not token:
        raise ValueError("Smoke embedding token is required")
    if (block_marker is None) != (request_marker is None):
        raise ValueError("Smoke blocking markers must be configured together")
    handler_type = type(
        "ConfiguredEmbeddingHandler",
        (_EmbeddingHandler,),
        {
            "token": token,
            "failure_marker": failure_marker,
            "block_marker": block_marker,
            "request_marker": request_marker,
        },
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler_type)


class _EmbeddingHandler(BaseHTTPRequestHandler):
    token = ""
    failure_marker: Path | None = None
    block_marker: Path | None = None
    request_marker: Path | None = None

    def do_POST(self) -> None:
        if self.path != "/v1/embeddings":
            self._write_json(404, {"error": {"message": "Not found"}})
            return
        if self.headers.get("Authorization") != f"Bearer {self.token}":
            self._write_json(401, {"error": {"message": "Unauthorized"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            inputs = _normalize_inputs(payload.get("input"))
        except (AttributeError, json.JSONDecodeError, ValueError):
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return
        if self.failure_marker is not None and self.failure_marker.exists():
            self._write_json(
                503,
                {
                    "error": {
                        "message": "The smoke embedding model is unavailable.",
                        "type": "server_error",
                        "code": "model_unavailable",
                    }
                },
            )
            return
        if self.block_marker is not None and self.block_marker.exists():
            assert self.request_marker is not None
            self.request_marker.write_text("request_received\n", encoding="utf-8")
            deadline = time.monotonic() + 30
            while self.block_marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if self.block_marker.exists():
                self._write_json(
                    503,
                    {"error": {"message": "Smoke embedding request timed out."}},
                )
                return
        data = [
            {
                "object": "embedding",
                "index": index,
                "embedding": _embedding(value),
            }
            for index, value in enumerate(inputs)
        ]
        self._write_json(
            200,
            {
                "object": "list",
                "data": data,
                "model": str(payload.get("model", "smoke-embedding")),
                "usage": {
                    "prompt_tokens": sum(_input_size(value) for value in inputs),
                    "total_tokens": sum(_input_size(value) for value in inputs),
                },
            },
        )

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: Any) -> None:
        return


def _normalize_inputs(value: Any) -> list[str | list[int]]:
    inputs = value if isinstance(value, list) else [value]
    if not inputs or any(not _valid_input(item) for item in inputs):
        raise ValueError("Embedding input must contain text")
    return inputs


def _valid_input(value: Any) -> bool:
    return isinstance(value, str) or (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, int) for item in value)
    )


def _input_size(value: str | list[int]) -> int:
    return len(value) if isinstance(value, list) else len(value.split())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve deterministic embeddings for packaged Desktop smoke tests."
    )
    parser.add_argument("--port-file", required=True, type=Path)
    parser.add_argument("--token", default="mara-desktop-smoke")
    parser.add_argument("--failure-marker", type=Path)
    parser.add_argument("--block-marker", type=Path)
    parser.add_argument("--request-marker", type=Path)
    arguments = parser.parse_args()
    server = create_server(
        arguments.token,
        failure_marker=arguments.failure_marker,
        block_marker=arguments.block_marker,
        request_marker=arguments.request_marker,
    )
    arguments.port_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.port_file.write_text(f"{server.server_port}\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
