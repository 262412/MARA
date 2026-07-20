from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

_BASELINE_DIR = Path(__file__).resolve().parent / "baselines"


def load_baseline_registry(baseline_id: str) -> dict[str, Any]:
    path = _BASELINE_DIR / f"{baseline_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown benchmark baseline: {baseline_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_registry_paths() -> list[Path]:
    return sorted(_BASELINE_DIR.glob("*.json"))


def assert_writable_benchmark_output(
    output_dir: str | Path,
    registry_paths: Iterable[Path] | None = None,
) -> None:
    target = Path(output_dir).resolve()
    paths = list(registry_paths or baseline_registry_paths())
    for path in paths:
        registry = json.loads(path.read_text(encoding="utf-8"))
        if not registry.get("immutable"):
            continue
        root_value = str(registry.get("artifact_root") or "").strip()
        if not root_value:
            continue
        root = Path(root_value).resolve()
        if target == root or root in target.parents:
            baseline_id = str(registry.get("baseline_id") or path.stem)
            raise ValueError(
                f"Output is inside frozen benchmark baseline {baseline_id}: {target}"
            )
