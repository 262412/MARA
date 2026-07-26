import json

import pytest

import benchmark.run_provenance as provenance


def test_run_contract_hash_covers_git_manifest_config_and_service_state(
    monkeypatch,
    tmp_path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dataset_name": "frozen"}), encoding="utf-8")
    monkeypatch.setattr(provenance, "_git_state", lambda _root: ("abc123", False))

    first = provenance.benchmark_run_provenance(
        manifest_path=manifest,
        config={"route": "all", "sample_seed": 7},
        repo_root=tmp_path,
        environ={
            "MARA_TEXT_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
            "MARA_BENCHMARK_SERVICE_CONTRACT": "qwen-script-sha",
        },
    )
    repeated = provenance.benchmark_run_provenance(
        manifest_path=manifest,
        config={"sample_seed": 7, "route": "all"},
        repo_root=tmp_path,
        environ={
            "MARA_BENCHMARK_SERVICE_CONTRACT": "qwen-script-sha",
            "MARA_TEXT_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
        },
    )
    changed = provenance.benchmark_run_provenance(
        manifest_path=manifest,
        config={"route": "all", "sample_seed": 8},
        repo_root=tmp_path,
        environ={
            "MARA_TEXT_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
            "MARA_BENCHMARK_SERVICE_CONTRACT": "qwen-script-sha",
        },
    )

    assert first["contract_hash"] == repeated["contract_hash"]
    assert first["contract_hash"] != changed["contract_hash"]
    assert first["git"] == {"commit": "abc123", "dirty": False}
    assert first["manifest"]["sha256"]
    assert first["service"]["contract"] == "qwen-script-sha"


def test_run_provenance_captures_all_runtime_endpoints_without_redefining_contract(
    monkeypatch,
    tmp_path,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dataset_name": "frozen"}), encoding="utf-8")
    monkeypatch.setattr(provenance, "_git_state", lambda _root: ("abc123", False))
    common = {
        "MARA_BENCHMARK_SERVICE_CONTRACT": "service-contract",
        "MARA_TEXT_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
        "MARA_RETRIEVAL_BASE_URL": "http://127.0.0.1:8002",
        "MARA_VLM_BASE_URL": "http://127.0.0.1:8001/v1",
        "MARA_COLVISION_ENDPOINT": "http://127.0.0.1:8003/visual-score",
    }

    first = provenance.benchmark_run_provenance(
        manifest_path=manifest,
        config={"route": "all"},
        repo_root=tmp_path,
        environ=common,
    )
    moved = provenance.benchmark_run_provenance(
        manifest_path=manifest,
        config={"route": "all"},
        repo_root=tmp_path,
        environ={
            **common,
            "MARA_COLVISION_ENDPOINT": "http://127.0.0.1:18003/visual-score",
        },
    )

    assert first["service"]["colvision_endpoint"].endswith("/visual-score")
    assert first["contract_hash"] == moved["contract_hash"]
    assert first["execution_hash"] != moved["execution_hash"]


def test_paired_contract_check_rejects_mismatched_runs():
    with pytest.raises(ValueError, match="run contract mismatch"):
        provenance.require_matching_run_contracts(
            {"run_provenance": {"contract_hash": "left"}},
            {"run_provenance": {"contract_hash": "right"}},
        )
