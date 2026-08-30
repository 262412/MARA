from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def source_packing_lineage(context: Any) -> dict[str, Any]:
    raw = getattr(context, "source_packing_observation", None)
    if not isinstance(raw, Mapping):
        return empty_source_packing_lineage("not_available")
    observation = dict(raw)
    observation["status"] = "passed"
    observation["source_records"] = _mapping_list(observation.get("source_records"))
    observation["records"] = _mapping_list(observation.get("records"))
    observation["canonical_records"] = _mapping_list(
        observation.get("canonical_records")
    )
    return observation


def empty_source_packing_lineage(status: str = "not_run") -> dict[str, Any]:
    return {
        "status": status,
        "contract_id": "",
        "source_records": [],
        "records": [],
        "canonical_records": [],
        "selector_crosswalk": {},
        "dropped_count": 0,
        "truncated_count": 0,
    }


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
