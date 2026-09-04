from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from scripts.slurm.smoke_openai_tool_calls import run_smoke


class _OpenAIHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def do_GET(self) -> None:  # noqa: N802
        self._write({"data": [{"id": "Qwen/Qwen3-8B"}]})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        payload: dict[str, Any] = json.loads(self.rfile.read(length))
        self.requests.append(payload)
        tool_name = ""
        if payload.get("tools"):
            tool_name = payload["tools"][0]["function"]["name"]
        if tool_name:
            message: dict[str, Any] = {
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": (
                                '{"evidences":["Alpha evidence."]}'
                                if tool_name == "CiteEvidence"
                                else '{"value":"ok"}'
                            ),
                        },
                    }
                ],
            }
        else:
            message = {"content": "pong"}
        self._write({"choices": [{"message": message}]})

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _write(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_openai_tool_call_smoke_executes_text_required_auto_and_citation_paths():
    _OpenAIHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenAIHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = run_smoke(
            f"http://127.0.0.1:{server.server_port}/v1",
            timeout_seconds=2,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert result["status"] == "passed"
    assert result["text_completion"] is True
    assert result["required_tool_call"] is True
    assert result["auto_tool_call"] is True
    assert result["citation_request"] is True
    assert result["citation_tool_call_error_count"] == 0
    assert result["inline_structured_citation_path_executed"] is True
    assert [request.get("tool_choice") for request in _OpenAIHandler.requests] == [
        None,
        "required",
        "auto",
        "required",
    ]
