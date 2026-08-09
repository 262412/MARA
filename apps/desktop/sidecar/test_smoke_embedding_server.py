from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .smoke_embedding_server import (
    _embedding,
    _EmbeddingHandler,
    _parse_arguments,
    create_server,
)


class _DisconnectedWriter:
    def write(self, _body: bytes) -> None:
        raise BrokenPipeError


class SmokeEmbeddingServerTest(unittest.TestCase):
    def test_accepts_a_deterministic_port_for_cross_version_smoke(self) -> None:
        arguments = _parse_arguments(
            ["--port-file", "/tmp/mara-smoke-port", "--port", "43127"]
        )

        self.assertEqual(arguments.port, 43127)

    def test_query_smoke_phrases_share_one_deterministic_embedding(self) -> None:
        self.assertEqual(
            _embedding("What does the deterministic query source say?"),
            _embedding(
                "The deterministic query source says that MARA Desktop preserves evidence."
            ),
        )

    def test_ignores_a_client_disconnect_while_writing_a_smoke_response(self) -> None:
        handler: Any = object.__new__(_EmbeddingHandler)
        handler.wfile = _DisconnectedWriter()
        handler.send_response = lambda _status_code: None
        handler.send_header = lambda _name, _value: None
        handler.end_headers = lambda: None

        handler._write_json(200, {"data": []})

    def test_serves_deterministic_openai_compatible_embeddings(self) -> None:
        server = create_server("smoke-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/embeddings",
                data=json.dumps(
                    {"input": ["paper", [1, 2, 3]], "model": "smoke-embedding"}
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer smoke-token",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                payload = json.load(response)

            self.assertEqual(response.status, 200)
            self.assertEqual([item["index"] for item in payload["data"]], [0, 1])
            self.assertEqual(len(payload["data"][0]["embedding"]), 16)
            self.assertEqual(
                payload["data"][0]["embedding"],
                payload["data"][0]["embedding"],
            )
            self.assertNotEqual(
                payload["data"][0]["embedding"],
                payload["data"][1]["embedding"],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_can_return_constant_embeddings_for_query_smoke(self) -> None:
        server = create_server("smoke-token", constant_embeddings=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/embeddings",
                data=json.dumps(
                    {"input": ["source", [1, 2, 3]], "model": "smoke-embedding"}
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer smoke-token",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                payload = json.load(response)

            self.assertEqual(
                payload["data"][0]["embedding"],
                payload["data"][1]["embedding"],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_serves_deterministic_openai_compatible_streaming_chat(self) -> None:
        server = create_server("smoke-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(_chat_request(server.server_port), timeout=2) as response:
                body = response.read().decode("utf-8")

            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "text/event-stream")
            self.assertIn("MARA Desktop", body)
            self.assertIn("CITATION【1】", body)
            self.assertIn("FINAL ANSWER", body)
            self.assertIn("data: [DONE]", body)
            self.assertNotIn("/private", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_chat_block_marker_exposes_a_partial_stream_then_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker_root = Path(temporary_directory)
            block_marker = marker_root / "chat-block"
            request_marker = marker_root / "chat-request"
            block_marker.touch()
            server = create_server(
                "smoke-token",
                chat_block_marker=block_marker,
                chat_request_marker=request_marker,
            )
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            outcomes: list[str | OSError] = []

            def request_chat() -> None:
                try:
                    with urlopen(
                        _chat_request(server.server_port), timeout=3
                    ) as response:
                        outcomes.append(response.read().decode("utf-8"))
                except OSError as exc:
                    outcomes.append(exc)

            request_thread = threading.Thread(target=request_chat, daemon=True)
            request_thread.start()
            try:
                self.assertTrue(_wait_for_path(request_marker))
                self.assertTrue(request_thread.is_alive())
                block_marker.unlink()
                request_thread.join(timeout=3)
                self.assertEqual(len(outcomes), 1)
                self.assertIsInstance(outcomes[0], str)
                self.assertIn("data: [DONE]", str(outcomes[0]))
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

    def test_failure_marker_returns_model_unavailable_then_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "model-unavailable"
            server = create_server("smoke-token", failure_marker=marker)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                marker.touch()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(_embedding_request(server.server_port), timeout=2)
                self.assertEqual(caught.exception.code, 503)
                payload = json.loads(caught.exception.read())
                self.assertEqual(payload["error"]["code"], "model_unavailable")

                marker.unlink()
                with urlopen(
                    _embedding_request(server.server_port), timeout=2
                ) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_block_marker_pauses_one_request_until_it_is_released(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker_root = Path(temporary_directory)
            block_marker = marker_root / "block"
            request_marker = marker_root / "request"
            block_marker.touch()
            server = create_server(
                "smoke-token",
                block_marker=block_marker,
                request_marker=request_marker,
            )
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            outcomes: list[int | OSError] = []

            def request_embedding() -> None:
                try:
                    with urlopen(
                        _embedding_request(server.server_port), timeout=2
                    ) as response:
                        outcomes.append(response.status)
                except OSError as exc:
                    outcomes.append(exc)

            request_thread = threading.Thread(target=request_embedding, daemon=True)
            request_thread.start()
            try:
                self.assertTrue(_wait_for_path(request_marker))
                self.assertTrue(request_thread.is_alive())
                block_marker.unlink()
                request_thread.join(timeout=2)
                self.assertEqual(outcomes, [200])
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)


def _embedding_request(port: int) -> Request:
    return Request(
        f"http://127.0.0.1:{port}/v1/embeddings",
        data=json.dumps({"input": ["paper"], "model": "smoke-embedding"}).encode(
            "utf-8"
        ),
        headers={
            "Authorization": "Bearer smoke-token",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _chat_request(port: int) -> Request:
    return Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(
            {
                "model": "smoke-chat",
                "messages": [{"role": "user", "content": "Question"}],
                "stream": True,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": "Bearer smoke-token",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _wait_for_path(path: Path) -> bool:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.01)
    return False
