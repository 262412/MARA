from pathlib import Path

from scripts.slurm import qasper_debug_contract_probe as probe


def test_probe_write_replaces_artifact_without_duplicate_rows(tmp_path: Path) -> None:
    path = tmp_path / "contract_probe_predictions.jsonl"
    rows = [{"example_id": "one"}, {"example_id": "two"}]
    probe._write_rows(path, rows)
    probe._write_rows(path, rows)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
