from __future__ import annotations

import json
import sys
import types

from benchmark.cli import main


def test_check_multimodal_backends_cli_writes_json_and_uses_strict_exit(
    monkeypatch,
    tmp_path,
):
    captured = {}

    def fake_check_multimodal_backends(*, timeout_seconds):
        captured["timeout_seconds"] = timeout_seconds
        return {
            "schema_version": 1,
            "overall_status": "blocked",
            "failure_taxonomy": [
                {
                    "role": "vlm",
                    "failure_type": "unreachable",
                    "status": "blocked",
                }
            ],
            "backends": {
                "vlm": {
                    "role": "vlm",
                    "status": "blocked",
                    "failure_type": "unreachable",
                }
            },
        }

    monkeypatch.setitem(
        sys.modules,
        "benchmark.multimodal_backend_health",
        types.SimpleNamespace(check_multimodal_backends=fake_check_multimodal_backends),
    )

    output_path = tmp_path / "backend-health.json"
    exit_code = main(
        [
            "check-multimodal-backends",
            "--output",
            str(output_path),
            "--timeout-seconds",
            "2.5",
            "--strict",
        ]
    )

    assert exit_code == 2
    assert captured["timeout_seconds"] == 2.5
    assert json.loads(output_path.read_text(encoding="utf-8"))["failure_taxonomy"] == [
        {
            "role": "vlm",
            "failure_type": "unreachable",
            "status": "blocked",
        }
    ]
