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
    if isinstance(value, str) and "deterministic query source" in value.lower():
        canonical = "mara-desktop-query-source"
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    values = [(value - 127.5) / 127.5 for value in digest[:16]]
    magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / magnitude for value in values]


def create_server(
    token: str,
    port: int = 0,
    *,
    constant_embeddings: bool = False,
    failure_marker: Path | None = None,
    block_marker: Path | None = None,
    request_marker: Path | None = None,
    chat_block_marker: Path | None = None,
    chat_request_marker: Path | None = None,
    chat_capture: Path | None = None,
) -> ThreadingHTTPServer:
    if not token:
        raise ValueError("Smoke embedding token is required")
    if (block_marker is None) != (request_marker is None):
        raise ValueError("Smoke blocking markers must be configured together")
    if (chat_block_marker is None) != (chat_request_marker is None):
        raise ValueError("Smoke chat markers must be configured together")
    handler_type = type(
        "ConfiguredEmbeddingHandler",
        (_EmbeddingHandler,),
        {
            "token": token,
            "constant_embeddings": constant_embeddings,
            "failure_marker": failure_marker,
            "block_marker": block_marker,
            "request_marker": request_marker,
            "chat_block_marker": chat_block_marker,
            "chat_request_marker": chat_request_marker,
            "chat_capture": chat_capture,
        },
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler_type)


class _EmbeddingHandler(BaseHTTPRequestHandler):
    token = ""
    constant_embeddings = False
    failure_marker: Path | None = None
    block_marker: Path | None = None
    request_marker: Path | None = None
    chat_block_marker: Path | None = None
    chat_request_marker: Path | None = None
    chat_capture: Path | None = None

    def do_POST(self) -> None:
        if self.path not in {"/v1/embeddings", "/v1/chat/completions"}:
            self._write_json(404, {"error": {"message": "Not found"}})
            return
        if self.headers.get("Authorization") != f"Bearer {self.token}":
            self._write_json(401, {"error": {"message": "Unauthorized"}})
            return
        payload = self._read_payload()
        if payload is None:
            return
        if self.path == "/v1/chat/completions":
            self._write_chat_completion(payload)
            return
        self._write_embeddings(payload)

    def _read_payload(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (AttributeError, json.JSONDecodeError, ValueError):
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return None
        if not isinstance(payload, dict):
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return None
        return payload

    def _write_embeddings(self, payload: dict[str, Any]) -> None:
        try:
            inputs = _normalize_inputs(payload.get("input"))
        except ValueError:
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
                "embedding": _embedding(
                    "mara-desktop-constant-embedding"
                    if self.constant_embeddings
                    else value
                ),
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

    def _write_chat_completion(self, payload: dict[str, Any]) -> None:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            self._write_json(400, {"error": {"message": "Invalid request"}})
            return
        model = str(payload.get("model") or "smoke-chat")
        self._capture_chat_route(model, bool(payload.get("stream")))
        answer = (
            "CITATION LIST\n\n"
            "CITATION【1】\n\n"
            "START_PHRASE: The deterministic query source alpha says\n"
            "END_PHRASE: preserves grounded evidence identities.\n\n"
            "CITATION【2】\n\n"
            "START_PHRASE: The deterministic query source beta says\n"
            "END_PHRASE: keeps cross-file citations distinct.\n\n"
            "FINAL ANSWER\n"
            "MARA Desktop preserves grounded evidence identities and keeps "
            "cross-file citations distinct.【1】【2】"
        )
        if not payload.get("stream"):
            self._write_json(
                200,
                {
                    "id": "chatcmpl-mara-desktop-smoke",
                    "object": "chat.completion",
                    "created": 1_786_147_200,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": answer},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 8,
                        "completion_tokens": 6,
                        "total_tokens": 14,
                    },
                },
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        chunks = [
            (
                "CITATION LIST\n\n"
                "CITATION【1】\n\n"
                "START_PHRASE: The deterministic query source alpha says\n"
                "END_PHRASE: preserves grounded evidence identities.\n\n"
                "CITATION【2】\n\n"
                "START_PHRASE: The deterministic query source beta says\n"
                "END_PHRASE: keeps cross-file citations distinct.\n\n"
                "FINAL ANSWER\n"
            ),
            "MARA Desktop preserves grounded evidence identities and keeps ",
            "cross-file citations distinct.【1】【2】",
        ]
        for index, content in enumerate(chunks):
            if index == 2 and self.chat_block_marker is not None:
                assert self.chat_request_marker is not None
                self.chat_request_marker.write_text(
                    "request_received\n",
                    encoding="utf-8",
                )
                deadline = time.monotonic() + 30
                while self.chat_block_marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
            if not self._write_sse_chunk(model, content):
                return
        self._write_sse_chunk(model, "", finish_reason="stop")
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def _capture_chat_route(self, model: str, stream: bool) -> None:
        if self.chat_capture is None:
            return
        self.chat_capture.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"model": model, "stream": stream}, sort_keys=True)
        self.chat_capture.write_text(f"{payload}\n", encoding="utf-8")

    def _write_sse_chunk(
        self,
        model: str,
        content: str,
        *,
        finish_reason: str | None = None,
    ) -> bool:
        payload = {
            "id": "chatcmpl-mara-desktop-smoke",
            "object": "chat.completion.chunk",
            "created": 1_786_147_200,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": finish_reason,
                }
            ],
        }
        body = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return False
        return True

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

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


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve deterministic embeddings for packaged Desktop smoke tests."
    )
    parser.add_argument("--port-file", required=True, type=Path)
    parser.add_argument("--port", default=0, type=int)
    parser.add_argument("--token", default="mara-desktop-smoke")
    parser.add_argument(
        "--constant-embeddings",
        action="store_true",
        help="Return one fixed embedding for deterministic query smoke tests.",
    )
    parser.add_argument("--failure-marker", type=Path)
    parser.add_argument("--block-marker", type=Path)
    parser.add_argument("--request-marker", type=Path)
    parser.add_argument("--chat-block-marker", type=Path)
    parser.add_argument("--chat-request-marker", type=Path)
    parser.add_argument("--chat-capture", type=Path)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = _parse_arguments()
    server = create_server(
        arguments.token,
        arguments.port,
        constant_embeddings=arguments.constant_embeddings,
        failure_marker=arguments.failure_marker,
        block_marker=arguments.block_marker,
        request_marker=arguments.request_marker,
        chat_block_marker=arguments.chat_block_marker,
        chat_request_marker=arguments.chat_request_marker,
        chat_capture=arguments.chat_capture,
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
