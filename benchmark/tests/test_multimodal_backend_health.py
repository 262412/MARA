from __future__ import annotations

import json
import urllib.error
from io import BytesIO

from benchmark.multimodal_backend_health import (
    DEFAULT_MULTIMODAL_BACKENDS,
    check_multimodal_backends,
    summarize_backend_failures,
)


class _Response(BytesIO):
    def __init__(self, payload: dict, *, status: int = 200):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_check_multimodal_backends_records_ready_ports_and_models(monkeypatch):
    payloads: dict[str, dict] = {
        "http://127.0.0.1:8000/v1/models": {
            "data": [{"id": "Qwen/Qwen3-8B"}],
        },
        "http://127.0.0.1:8001/v1/models": {
            "data": [{"id": "Qwen/Qwen3-VL-8B-Instruct"}],
        },
        "http://127.0.0.1:8002/health": {
            "ok": True,
            "model": "BAAI/bge-m3",
        },
        "http://127.0.0.1:8003/health": {
            "ok": True,
            "model_family": "colqwen",
            "device": "cuda:0",
        },
    }

    def fake_urlopen(request, timeout):
        assert timeout == 1.5
        return _Response(payloads[request.full_url])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = check_multimodal_backends(
        timeout_seconds=1.5,
        checked_at="2026-06-29T12:00:00+00:00",
    )

    assert result["schema_version"] == 1
    assert result["checked_at"] == "2026-06-29T12:00:00+00:00"
    assert result["overall_status"] == "ready"
    assert result["backends"]["text_llm"]["status"] == "ready"
    assert result["backends"]["text_llm"]["models"] == ["Qwen/Qwen3-8B"]
    assert result["backends"]["vlm"]["status"] == "ready"
    assert result["backends"]["vlm"]["models"] == ["Qwen/Qwen3-VL-8B-Instruct"]
    assert result["backends"]["retrieval"]["status"] == "ready"
    assert result["backends"]["colvision"]["model_family"] == "colqwen"
    assert result["backends"]["colvision"]["device"] == "cuda:0"
    assert result["failure_taxonomy"] == []


def test_check_multimodal_backends_classifies_service_failures(monkeypatch):
    def fake_urlopen(request, timeout):
        url = request.full_url
        if url.endswith("8000/v1/models"):
            return _Response({"data": [{"id": "Qwen/Qwen3-8B"}]})
        if url.endswith("8001/v1/models"):
            raise urllib.error.URLError(ConnectionRefusedError("refused"))
        if url.endswith("8002/health"):
            return _Response({"ok": False, "error": "embedding model loading"})
        return _Response({"ok": True, "model_family": "colpali"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = check_multimodal_backends()

    assert result["overall_status"] == "blocked"
    assert result["backends"]["vlm"]["status"] == "blocked"
    assert result["backends"]["vlm"]["failure_type"] == "unreachable"
    assert result["backends"]["retrieval"]["failure_type"] == "health_not_ok"
    assert result["backends"]["colvision"]["failure_type"] == "family_mismatch"
    assert summarize_backend_failures(result) == [
        {
            "role": "vlm",
            "failure_type": "unreachable",
            "status": "blocked",
        },
        {
            "role": "retrieval",
            "failure_type": "health_not_ok",
            "status": "blocked",
        },
        {
            "role": "colvision",
            "failure_type": "family_mismatch",
            "status": "blocked",
        },
    ]


def test_default_multimodal_backend_contract_covers_required_ports():
    endpoints = {backend.role: backend.url for backend in DEFAULT_MULTIMODAL_BACKENDS}

    assert endpoints == {
        "text_llm": "http://127.0.0.1:8000/v1/models",
        "vlm": "http://127.0.0.1:8001/v1/models",
        "retrieval": "http://127.0.0.1:8002/health",
        "colvision": "http://127.0.0.1:8003/health",
    }
