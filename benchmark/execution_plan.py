from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_publication import atomic_write_json, file_sha256
from .execution_ledger import write_plan_and_table as _write_plan_and_table
from .jsonl import read_jsonl
from .sampling import select_examples

PLAN_SCHEMA_VERSION = "benchmark_execution_plan.v1"


@dataclass(frozen=True)
class JobDefinition:
    kind: str
    dataset: str
    route: str
    shard_index: int
    num_shards: int
    limit: int
    timeout_seconds: int
    suite_name: str
    manifest: Path
    output_root: Path


def parse_job_spec(value: str) -> JobDefinition:
    fields = value.split(",")
    if len(fields) != 10:
        raise ValueError(
            "job spec must contain kind,dataset,route,shard_index,num_shards,"
            "limit,timeout_seconds,suite_name,manifest,output_root"
        )
    return JobDefinition(
        kind=fields[0],
        dataset=fields[1],
        route=fields[2],
        shard_index=int(fields[3]),
        num_shards=int(fields[4]),
        limit=int(fields[5]),
        timeout_seconds=int(fields[6]),
        suite_name=fields[7],
        manifest=Path(fields[8]).resolve(),
        output_root=Path(fields[9]).resolve(),
    )


def build_execution_plan(
    definitions: list[JobDefinition],
    *,
    output_plan: Path,
    output_table: Path,
    source_sha: str,
    sample_seed: int,
) -> dict[str, Any]:
    if not definitions:
        raise ValueError("execution plan must contain at least one job")
    plan_dir = output_plan.resolve().parent
    contract_dir = plan_dir / "job_contracts"
    contract_dir.mkdir(parents=True, exist_ok=True)

    jobs, groups = _build_jobs(definitions, sample_seed, contract_dir)
    _finalize_groups(groups, jobs, plan_dir)

    plan_payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "source_sha": source_sha,
        "sample_seed": sample_seed,
        "jobs": jobs,
        "groups": list(groups.values()),
        "canonical_counts": [
            {
                "dataset": job["dataset"],
                "manifest": job["manifest"],
                "manifest_sha256": job["manifest_sha256"],
                "route": job["route"],
                "shard_index": job["shard_index"],
                "num_shards": job["num_shards"],
                "selected_example_count": len(job["selected_example_ids"]),
                "route_count": len(job["expected_route_ids"]),
                "expected_prediction_count": job["expected_key_count"],
            }
            for job in jobs
        ],
    }
    plan_payload["expected_union_key_count"] = sum(
        group["expected_full_key_count"] for group in groups.values()
    )
    plan_payload["plan_sha256"] = _payload_sha256(plan_payload)
    for job in jobs:
        atomic_write_json(
            Path(job["contract_path"]),
            {
                "schema_version": "benchmark_execution_contract.v1",
                "plan_sha256": plan_payload["plan_sha256"],
                "job_key": job["job_key"],
                "group_key": job["group_key"],
                "dataset": job["dataset"],
                "manifest": job["manifest"],
                "manifest_sha256": job["manifest_sha256"],
                "execution_manifest": job["execution_manifest"],
                "execution_manifest_sha256": job["execution_manifest_sha256"],
                "selected_example_ids": job["selected_example_ids"],
                "expected_route_ids": job["expected_route_ids"],
                "expected_keys": job["expected_keys"],
                "expected_count": job["expected_key_count"],
                "expected_key_sha256": job["expected_key_sha256"],
            },
        )
    _write_plan_and_table(plan_payload, output_plan, output_table)
    return plan_payload


def _build_jobs(
    definitions: list[JobDefinition],
    sample_seed: int,
    contract_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    jobs: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    seen_job_keys: set[str] = set()
    manifest_cache: dict[Path, tuple[list[dict[str, Any]], list[str]]] = {}
    for definition in definitions:
        if definition.suite_name in seen_job_keys:
            raise ValueError(
                f"duplicate execution plan job key: {definition.suite_name}"
            )
        seen_job_keys.add(definition.suite_name)
        scope = _job_scope(definition, sample_seed, manifest_cache)
        group = _merge_group(groups, definition, scope)
        group["job_keys"].append(definition.suite_name)
        for example_id in scope["selected_ids"]:
            if example_id not in group["selected_example_ids"]:
                group["selected_example_ids"].append(example_id)
        jobs.append(_job_record(definition, scope, group["group_key"], contract_dir))
    return jobs, groups


def _job_scope(
    definition: JobDefinition,
    sample_seed: int,
    manifest_cache: dict[Path, tuple[list[dict[str, Any]], list[str]]],
) -> dict[str, Any]:
    if definition.manifest not in manifest_cache:
        manifest_cache[definition.manifest] = _load_manifest_selection(
            definition.manifest
        )
    examples, route_ids_for_manifest = manifest_cache[definition.manifest]
    selected = select_examples(
        examples,
        limit=definition.limit,
        sample_seed=sample_seed,
        shard_index=definition.shard_index,
        num_shards=definition.num_shards,
    )
    selected_ids = [
        _example_id(example, index) for index, example in enumerate(selected)
    ]
    manifest_example_ids = [
        _example_id(example, index) for index, example in enumerate(examples)
    ]
    if len(manifest_example_ids) != len(set(manifest_example_ids)):
        raise ValueError(
            f"manifest contains duplicate example IDs: {definition.manifest}"
        )
    route_ids = _active_route_ids(route_ids_for_manifest, definition.route)
    return {
        "examples": examples,
        "selected_ids": selected_ids,
        "route_ids": route_ids,
        "manifest_example_ids": manifest_example_ids,
        "manifest_route_ids": _active_route_ids(route_ids_for_manifest, "all"),
        "manifest_sha256": file_sha256(definition.manifest),
    }


def _merge_group(
    groups: dict[str, dict[str, Any]],
    definition: JobDefinition,
    scope: dict[str, Any],
) -> dict[str, Any]:
    group_key = _canonical_group_key(
        definition.dataset,
        scope["manifest_example_ids"],
        scope["manifest_route_ids"],
    )
    group = groups.setdefault(
        group_key,
        {
            "group_key": group_key,
            "dataset": definition.dataset,
            "manifest": str(definition.manifest),
            "manifest_sha256": scope["manifest_sha256"],
            "manifest_variants": [],
            "manifest_example_count": len(scope["examples"]),
            "manifest_example_ids": scope["manifest_example_ids"],
            "manifest_route_ids": scope["manifest_route_ids"],
            "selected_example_ids": [],
            "job_keys": [],
        },
    )
    if (
        group["manifest_example_ids"] != scope["manifest_example_ids"]
        or group["manifest_route_ids"] != scope["manifest_route_ids"]
    ):
        raise ValueError(
            "execution jobs with the same canonical group must share example and route identity: "
            f"{definition.manifest}"
        )
    variant = {"manifest": str(definition.manifest), "sha256": scope["manifest_sha256"]}
    if variant not in group["manifest_variants"]:
        group["manifest_variants"].append(variant)
    return group


def _job_record(
    definition: JobDefinition,
    scope: dict[str, Any],
    group_key: str,
    contract_dir: Path,
) -> dict[str, Any]:
    expected_keys = [
        [example_id, route_id]
        for example_id in scope["selected_ids"]
        for route_id in scope["route_ids"]
    ]
    return {
        "job_key": definition.suite_name,
        "group_key": group_key,
        "job_id": "",
        "wave_index": "",
        "dependency": "",
        "state": "PLANNED",
        "kind": definition.kind,
        "dataset": definition.dataset,
        "route": definition.route,
        "shard_index": definition.shard_index,
        "num_shards": definition.num_shards,
        "limit": definition.limit,
        "timeout_seconds": definition.timeout_seconds,
        "suite_name": definition.suite_name,
        "manifest": str(definition.manifest),
        "manifest_sha256": scope["manifest_sha256"],
        "execution_manifest": "",
        "execution_manifest_sha256": "",
        "manifest_example_count": len(scope["examples"]),
        "selected_example_ids": scope["selected_ids"],
        "expected_route_ids": scope["route_ids"],
        "expected_keys": expected_keys,
        "expected_key_count": len(expected_keys),
        "expected_key_sha256": _key_sha256(expected_keys),
        "output_root": str(definition.output_root),
        "contract_path": str(contract_dir / f"{_slug(definition.suite_name)}.json"),
        "artifact_complete": False,
        "artifact_digest": "",
        "artifact_dir": "",
        "exit_code": "",
        "slurm_state": "",
        "slurm_exit_code": "",
        "failure_reason": "",
        "producer_completion_state": "",
        "producer_exit_code": "",
        "producer_artifact_complete": False,
        "producer_artifact_digest": "",
        "producer_artifact_dir": "",
        "producer_failure_reason": "",
        "producer_completion_contract": "",
        "runtime_contract_path": "",
        "runtime_contract_sha256": "",
        "completion_reconciliation_contract": "",
    }


def _finalize_groups(
    groups: dict[str, dict[str, Any]],
    jobs: list[dict[str, Any]],
    plan_dir: Path,
) -> None:
    execution_manifest_dir = plan_dir / "execution_manifests"
    execution_manifest_dir.mkdir(parents=True, exist_ok=True)
    for group in groups.values():
        _finalize_group(group, jobs, execution_manifest_dir)


def _finalize_group(
    group: dict[str, Any],
    jobs: list[dict[str, Any]],
    execution_manifest_dir: Path,
) -> None:
    selected_set = set(group["selected_example_ids"])
    group["selected_example_ids"] = [
        example_id
        for example_id in group["manifest_example_ids"]
        if example_id in selected_set
    ]
    execution_manifest = execution_manifest_dir / f"{_slug(group['group_key'])}.json"
    _write_execution_manifest(
        Path(group["manifest"]),
        execution_manifest,
        selected_ids=set(group["selected_example_ids"]),
        route_ids=group["manifest_route_ids"],
    )
    group["execution_manifest"] = str(execution_manifest)
    group["execution_manifest_sha256"] = file_sha256(execution_manifest)
    group["selected_example_count"] = len(group["selected_example_ids"])
    group["expected_full_key_count"] = len(group["selected_example_ids"]) * len(
        group["manifest_route_ids"]
    )
    group["expected_full_key_sha256"] = _key_sha256(
        [
            [example_id, route_id]
            for example_id in group["selected_example_ids"]
            for route_id in group["manifest_route_ids"]
        ]
    )
    for job in jobs:
        if job["group_key"] == group["group_key"]:
            job["execution_manifest"] = group["execution_manifest"]
            job["execution_manifest_sha256"] = group["execution_manifest_sha256"]


def record_submission(
    plan_path: Path,
    table_path: Path,
    *,
    job_key: str,
    job_id: str,
    wave_index: int,
    dependency: str,
) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for job in plan.get("jobs", []):
        if job.get("job_key") == job_key:
            job.update(
                {
                    "job_id": job_id,
                    "wave_index": wave_index,
                    "dependency": dependency,
                    "state": "SUBMITTED",
                }
            )
            break
    else:
        raise ValueError(f"execution plan job not found: {job_key}")
    _write_plan_and_table(plan, plan_path, table_path)


def _active_route_ids(routes: list[str], requested_route: str) -> list[str]:
    route_ids = []
    for route in routes:
        route_id = str(route).strip()
        if not route_id or route_id in route_ids:
            raise ValueError(
                f"manifest contains duplicate or blank route_id: {route_id!r}"
            )
        route_ids.append(route_id)
    if requested_route in {"all", "*", ""}:
        return route_ids or ["all"]
    if requested_route in route_ids:
        return [requested_route]
    return [requested_route]


def _load_manifest_selection(
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    if manifest_path.suffix.lower() == ".jsonl":
        payload: Any = read_jsonl(manifest_path)
        examples = payload
        routes_payload: list[Any] = []
    else:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            examples = payload
            routes_payload = []
        elif isinstance(payload, dict):
            examples = payload.get("examples", [])
            routes_payload = payload.get("routes") or payload.get("route_matrix") or []
        else:
            raise ValueError(
                f"manifest must contain an object or list: {manifest_path}"
            )
    if not isinstance(examples, list) or any(
        not isinstance(item, dict) for item in examples
    ):
        raise ValueError(f"manifest examples must be objects: {manifest_path}")
    if not isinstance(routes_payload, list) or any(
        not isinstance(item, dict) for item in routes_payload
    ):
        raise ValueError(f"manifest routes must be objects: {manifest_path}")
    route_ids = []
    for index, route in enumerate(routes_payload, start=1):
        route_ids.append(
            str(
                route.get("route_id")
                or route.get("id")
                or route.get("route")
                or route.get("name")
                or f"route_{index}"
            ).strip()
        )
    return examples, route_ids


def _example_id(example: dict[str, Any], index: int) -> str:
    explicit = str(example.get("example_id") or "").strip()
    if explicit:
        return explicit
    document_ids = example.get("document_ids") or example.get("document_id")
    if isinstance(document_ids, list):
        document_id = str(document_ids[0]) if document_ids else "document"
    else:
        document_id = str(document_ids or "document")
    return f"{document_id}_{index}"


def _write_execution_manifest(
    source_path: Path,
    output_path: Path,
    *,
    selected_ids: set[str],
    route_ids: list[str],
) -> None:
    if source_path.suffix.lower() == ".jsonl":
        source_examples = [dict(value) for value in read_jsonl(source_path)]
        payload: dict[str, Any] = {
            "schema_version": 2,
            "dataset_name": source_path.stem,
            "documents": [],
            "examples": source_examples,
            "routes": [],
        }
    else:
        source_payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        if isinstance(source_payload, list):
            payload = {
                "schema_version": 2,
                "dataset_name": source_path.stem,
                "documents": [],
                "examples": source_payload,
                "routes": [],
            }
        elif isinstance(source_payload, dict):
            payload = dict(source_payload)
            payload["examples"] = list(payload.get("examples") or [])
            payload["routes"] = list(
                payload.get("routes") or payload.get("route_matrix") or []
            )
        else:
            raise ValueError(f"manifest must contain an object or list: {source_path}")
    payload["examples"] = [
        example
        for index, example in enumerate(payload["examples"])
        if isinstance(example, dict) and _example_id(example, index) in selected_ids
    ]
    source_routes = payload.get("routes")
    if source_routes:
        payload["routes"] = [
            route
            for index, route in enumerate(source_routes, start=1)
            if _route_id(route, index) in route_ids
        ]
    else:
        payload["routes"] = [{"route_id": route_id} for route_id in route_ids]
    payload["execution_scope"] = {
        "source_manifest": str(source_path),
        "selected_example_ids": sorted(selected_ids),
        "route_ids": route_ids,
    }
    atomic_write_json(output_path, payload)


def _route_id(route: dict[str, Any], index: int) -> str:
    return str(
        route.get("route_id")
        or route.get("id")
        or route.get("route")
        or route.get("name")
        or f"route_{index}"
    ).strip()


def _canonical_group_key(
    dataset: str,
    example_ids: list[str],
    route_ids: list[str],
) -> str:
    full_key_sha256 = _key_sha256(
        [[example_id, route_id] for example_id in example_ids for route_id in route_ids]
    )
    return f"{dataset}|{full_key_sha256}"


def _key_sha256(keys: list[list[str]]) -> str:
    canonical = "\n".join(
        f"{example_id}\t{route_id}" for example_id, route_id in sorted(keys)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _payload_sha256(payload: dict[str, Any]) -> str:
    content = dict(payload)
    content.pop("plan_sha256", None)
    return hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return slug or "job"
