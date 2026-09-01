from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


def build_manifest_subset(
    manifest: Mapping[str, Any], example_ids: Iterable[str]
) -> dict[str, Any]:
    """Return a schema-v2 manifest containing exactly the requested examples."""

    if int(manifest.get("schema_version") or 0) != 2:
        raise ValueError("manifest subset requires schema_version=2")
    requested = [str(value).strip() for value in example_ids if str(value).strip()]
    if not requested:
        raise ValueError("at least one example_id is required")
    if len(requested) != len(set(requested)):
        raise ValueError("example_ids must be unique")
    examples = _examples_by_id(manifest.get("examples"))
    missing = [example_id for example_id in requested if example_id not in examples]
    if missing:
        raise ValueError("manifest examples not found: " + ", ".join(missing))
    selected_examples = [deepcopy(examples[example_id]) for example_id in requested]
    selected_documents = _selected_documents(
        manifest.get("documents"), selected_examples
    )
    return {
        **deepcopy(dict(manifest)),
        "documents": selected_documents,
        "examples": selected_examples,
    }


def _examples_by_id(raw_examples: Any) -> dict[str, dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}
    for example in raw_examples or []:
        if not isinstance(example, Mapping):
            continue
        example_id = str(example.get("example_id") or "").strip()
        if not example_id:
            raise ValueError("manifest contains an example without example_id")
        if example_id in examples:
            raise ValueError(f"manifest contains duplicate example_id: {example_id}")
        examples[example_id] = dict(example)
    return examples


def _selected_documents(
    raw_documents: Any, examples: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    required_ids = {
        str(document_id).strip()
        for example in examples
        for document_id in (example.get("document_ids") or [example.get("document_id")])
        if str(document_id or "").strip()
    }
    selected = [
        deepcopy(dict(document))
        for document in raw_documents or []
        if isinstance(document, Mapping)
        and str(document.get("document_id") or "").strip() in required_ids
    ]
    found_ids = {
        str(document.get("document_id") or "").strip() for document in selected
    }
    if found_ids != required_ids:
        raise ValueError(
            "manifest documents not found: "
            + ", ".join(sorted(required_ids - found_ids))
        )
    return selected
