from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evidence_identity import EvidenceIdentity, identity_of


def _alias_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _alias_variants(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    path = Path(text)
    values = {text, path.name, path.stem}
    return {_alias_key(item) for item in values if _alias_key(item)}


@dataclass(frozen=True)
class SourceIdentityCrosswalk:
    canonical_dataset_id: str
    runtime_file_id: str = ""
    runtime_source_id: str = ""
    document_path: str = ""
    filename: str = ""
    aliases: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_dataset_id": self.canonical_dataset_id,
            "runtime_file_id": self.runtime_file_id,
            "runtime_source_id": self.runtime_source_id,
            "document_path": self.document_path,
            "filename": self.filename,
            "aliases": list(self.aliases),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceIdentityCrosswalk:
        return cls(
            canonical_dataset_id=str(
                value.get("canonical_dataset_id") or value.get("document_id") or ""
            ).strip(),
            runtime_file_id=str(value.get("runtime_file_id") or "").strip(),
            runtime_source_id=str(value.get("runtime_source_id") or "").strip(),
            document_path=str(value.get("document_path") or "").strip(),
            filename=str(value.get("filename") or "").strip(),
            aliases=tuple(
                str(item).strip()
                for item in value.get("aliases") or []
                if str(item).strip()
            ),
        )

    def alias_values(self) -> set[str]:
        values = {
            self.canonical_dataset_id,
            self.runtime_file_id,
            self.runtime_source_id,
            self.document_path,
            self.filename,
            *self.aliases,
        }
        return {variant for value in values for variant in _alias_variants(value)}


class SourceIdentityResolver:
    def __init__(self, records: Iterable[Mapping[str, Any] | SourceIdentityCrosswalk]):
        self.records = [
            item
            if isinstance(item, SourceIdentityCrosswalk)
            else SourceIdentityCrosswalk.from_mapping(item)
            for item in records
        ]
        targets: dict[str, set[str]] = {}
        for record in self.records:
            if not record.canonical_dataset_id:
                continue
            for alias in record.alias_values():
                targets.setdefault(alias, set()).add(record.canonical_dataset_id)
        self._targets = targets
        self._canonical_targets = {
            _alias_key(record.canonical_dataset_id): record.canonical_dataset_id
            for record in self.records
            if record.canonical_dataset_id
        }

    @property
    def ambiguous_aliases(self) -> set[str]:
        return {alias for alias, targets in self._targets.items() if len(targets) > 1}

    @property
    def ambiguous_alias_count(self) -> int:
        return len(self.ambiguous_aliases)

    def resolve(self, value: Any) -> str:
        exact = self._canonical_targets.get(_alias_key(value))
        if exact:
            return exact
        resolved = {
            target
            for alias in _alias_variants(value)
            for target in self._targets.get(alias, set())
        }
        return next(iter(resolved)) if len(resolved) == 1 else ""

    def canonical_or_original(self, value: Any) -> str:
        return self.resolve(value) or str(value or "").strip()

    def unresolved_count(self, values: Iterable[Any]) -> int:
        return sum(1 for value in values if value and not self.resolve(value))


def canonicalize_evidence_source(
    item: Mapping[str, Any],
    records: Iterable[Mapping[str, Any] | SourceIdentityCrosswalk],
) -> dict[str, Any]:
    normalized = dict(item)
    resolver = SourceIdentityResolver(records)
    metadata = dict(normalized.get("metadata") or {})
    source_values = [
        normalized.get("source_id"),
        normalized.get("document_id"),
        normalized.get("file_id"),
        metadata.get("source_id"),
        metadata.get("document_id"),
        metadata.get("file_id"),
        normalized.get("source_name"),
        normalized.get("file_name"),
        metadata.get("file_name"),
    ]
    canonical = next(
        (resolved for value in source_values if (resolved := resolver.resolve(value))),
        "",
    )
    if not canonical:
        return normalized

    runtime_source = str(
        normalized.get("runtime_source_id")
        or normalized.get("source_id")
        or normalized.get("file_id")
        or metadata.get("file_id")
        or ""
    ).strip()
    runtime_source = runtime_source or canonical
    aliases = {
        str(value).strip()
        for value in [
            *source_values,
            *(normalized.get("source_aliases") or []),
        ]
        if str(value or "").strip()
    }
    aliases.add(canonical)
    runtime_identity = _identity_for_source(normalized, runtime_source)
    evaluation_identity = _identity_for_source(normalized, canonical)
    source_projection = _source_projection(
        runtime_source,
        canonical,
        aliases,
        runtime_identity,
        evaluation_identity,
    )
    normalized.update(source_projection)
    original_backrefs = [
        str(value).strip()
        for value in normalized.get("source_backrefs") or []
        if str(value).strip()
    ]
    evaluation_backrefs = [
        _canonical_backref(str(value), resolver) for value in original_backrefs
    ]
    normalized["runtime_source_backrefs"] = original_backrefs
    normalized["source_backrefs"] = evaluation_backrefs
    normalized["evaluation_source_backrefs"] = evaluation_backrefs
    metadata.update(source_projection)
    metadata.pop("identity", None)
    metadata.pop("canonical_id", None)
    metadata["runtime_source_backrefs"] = original_backrefs
    metadata["evaluation_source_backrefs"] = evaluation_backrefs
    normalized["metadata"] = metadata
    return normalized


def _source_projection(
    runtime_source: str,
    canonical_source: str,
    aliases: set[str],
    runtime_identity: EvidenceIdentity,
    evaluation_identity: EvidenceIdentity,
) -> dict[str, Any]:
    return {
        "runtime_source_id": runtime_source,
        "evaluation_source_id": canonical_source,
        "source_id": runtime_source,
        "document_id": canonical_source,
        "file_id": runtime_source,
        "source_aliases": sorted(aliases),
        "runtime_identity": runtime_identity.key,
        "evaluation_identity": evaluation_identity.key,
        "identity": runtime_identity.as_dict(),
        "canonical_id": runtime_identity.key,
    }


def canonicalize_evidence_sources(
    items: Iterable[Mapping[str, Any]],
    records: Iterable[Mapping[str, Any] | SourceIdentityCrosswalk],
) -> list[dict[str, Any]]:
    crosswalk = list(records)
    if not crosswalk:
        return [dict(item) for item in items]
    return [canonicalize_evidence_source(item, crosswalk) for item in items]


def _canonical_backref(value: str, resolver: SourceIdentityResolver) -> str:
    source, marker, suffix = value.partition("#")
    canonical = resolver.resolve(source)
    if not canonical:
        return value
    return f"{canonical}{marker}{suffix}" if marker else canonical


def _identity_for_source(
    item: Mapping[str, Any],
    source_id: str,
) -> EvidenceIdentity:
    projected = dict(item)
    metadata = dict(projected.get("metadata") or {})
    projected.update(
        {
            "source_id": source_id,
            "file_id": source_id,
            "runtime_source_id": source_id,
        }
    )
    metadata.update(
        {
            "source_id": source_id,
            "file_id": source_id,
            "runtime_source_id": source_id,
        }
    )
    projected["metadata"] = metadata
    projected.pop("identity", None)
    projected.pop("canonical_id", None)
    return identity_of(projected)
