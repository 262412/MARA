from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from ktem.docqa.benchmark_evidence import benchmark_evidence_record

_FROZEN_FUSION_STAGE_PROJECTIONS = frozenset(
    {
        "canonical_candidate_evidence",
        "candidate_evidence",
        "candidate_ranked_evidence",
        "fused_evidence",
    }
)


@dataclass(frozen=True)
class CanonicalEvidenceIdentity:
    source_id: str
    chunk_start: int | None
    chunk_end: int | None
    text_hash: str

    @property
    def sort_key(self) -> tuple[str, int, int, str]:
        return (
            self.source_id,
            self.chunk_start if self.chunk_start is not None else 2**63 - 1,
            self.chunk_end if self.chunk_end is not None else 2**63 - 1,
            self.text_hash,
        )


@dataclass(frozen=True)
class CanonicalQuoteSpan:
    source_id: str
    canonical_start: int | None
    canonical_end: int | None
    item_start: int
    item_end: int
    text_hash: str

    @property
    def identity(self) -> str:
        if self.canonical_start is not None and self.canonical_end is not None:
            locator = f"{self.canonical_start}:{self.canonical_end}"
        else:
            locator = f"{self.text_hash}:{self.item_start}:{self.item_end}"
        return f"quote:{self.source_id}:{locator}"


def canonical_evidence_identity(
    item: dict[str, Any],
    *,
    text: str,
) -> CanonicalEvidenceIdentity:
    record = benchmark_evidence_record(item)
    source_id = (
        record.evaluation_source_id
        or record.document_id
        or _stable_source_name(item)
        or record.source_id
        or "unknown-source"
    )
    text_hash = record.normalized_text_hash or _normalized_text_hash(text)
    chunk_start, chunk_end = _explicit_offsets(
        item, record.chunk_start, record.chunk_end
    )
    if chunk_start is None:
        source_text = _source_text(item)
        match = _unique_contiguous_match(source_text, text) if source_text else None
        if match is not None:
            chunk_start, chunk_end = match
    return CanonicalEvidenceIdentity(
        source_id=source_id,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        text_hash=text_hash,
    )


def canonical_evidence_sort_key(
    item: dict[str, Any],
    *,
    text: str,
) -> tuple[str, int, int, str]:
    return canonical_evidence_identity(item, text=text).sort_key


def canonical_quote_spans(
    item: dict[str, Any],
    quote: str,
    *,
    text: str,
) -> tuple[CanonicalQuoteSpan, ...]:
    item_matches = _contiguous_matches(text, quote)
    if not item_matches:
        return ()
    identity = canonical_evidence_identity(item, text=text)
    source_text = _source_text(item)
    source_matches = _contiguous_matches(source_text, quote) if source_text else []
    if len(source_matches) == 1:
        canonical_start, canonical_end = source_matches[0]
        item_start, item_end = item_matches[0]
        return (
            CanonicalQuoteSpan(
                source_id=identity.source_id,
                canonical_start=canonical_start,
                canonical_end=canonical_end,
                item_start=item_start,
                item_end=item_end,
                text_hash=identity.text_hash,
            ),
        )

    spans: list[CanonicalQuoteSpan] = []
    for item_start, item_end in item_matches:
        span_start = (
            identity.chunk_start + item_start
            if identity.chunk_start is not None
            else None
        )
        span_end = (
            identity.chunk_start + item_end
            if identity.chunk_start is not None
            else None
        )
        spans.append(
            CanonicalQuoteSpan(
                source_id=identity.source_id,
                canonical_start=span_start,
                canonical_end=span_end,
                item_start=item_start,
                item_end=item_end,
                text_hash=identity.text_hash,
            )
        )
    return tuple(spans)


def canonical_prompt_span(
    item: dict[str, Any],
    *,
    text: str,
    item_start: int,
    item_end: int,
) -> dict[str, Any]:
    identity = canonical_evidence_identity(item, text=text)
    canonical_start = (
        identity.chunk_start + item_start if identity.chunk_start is not None else None
    )
    canonical_end = (
        identity.chunk_start + item_end if identity.chunk_start is not None else None
    )
    return {
        "evaluation_source_id": identity.source_id,
        "canonical_span_start": canonical_start,
        "canonical_span_end": canonical_end,
        "item_span_start": item_start,
        "item_span_end": item_end,
        "normalized_text_hash": identity.text_hash,
    }


def stabilize_qasper_evidence_projection(
    metadata: dict[str, Any],
    retrieved_hits: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Order persisted QASPER evidence by canonical provenance, never runtime IDs."""

    normalized_metadata = dict(metadata)
    for key, value in list(normalized_metadata.items()):
        if not _is_evidence_projection_list(key, value):
            continue
        if _is_frozen_fusion_stage_projection(key, normalized_metadata):
            continue
        normalized_metadata[key] = _stable_evidence_order(value)
    return normalized_metadata, _stable_evidence_order(retrieved_hits)


def _is_frozen_fusion_stage_projection(
    key: str,
    metadata: dict[str, Any],
) -> bool:
    if key not in _FROZEN_FUSION_STAGE_PROJECTIONS:
        return False
    snapshot = metadata.get("fusion_stage_snapshot")
    ranking = metadata.get("ranking_trace")
    return bool(
        isinstance(snapshot, dict)
        and snapshot.get("contract_id") == "fusion_stage_snapshot.v1"
        and isinstance(ranking, dict)
        and ranking.get("fusion_stage_contract_id") == "fusion_stage_snapshot.v1"
    )


def _is_evidence_projection_list(key: str, value: Any) -> bool:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return False
    return key.endswith("_evidence") or key in {
        "evidence",
        "candidate_evidence",
        "candidate_ranked_evidence",
        "canonical_candidate_evidence",
        "reranker_input_evidence",
    }


def _stable_evidence_order(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: canonical_evidence_sort_key(
            item,
            text=_evidence_text(item),
        ),
    )


def _evidence_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _explicit_offsets(
    item: dict[str, Any],
    record_start: int | None,
    record_end: int | None,
) -> tuple[int | None, int | None]:
    raw_metadata = item.get("metadata")
    metadata = (
        cast(dict[str, Any], raw_metadata) if isinstance(raw_metadata, dict) else {}
    )
    raw_extension = item.get("extension_metadata")
    extension = (
        cast(dict[str, Any], raw_extension) if isinstance(raw_extension, dict) else {}
    )
    for start_key, end_key in (
        ("canonical_start", "canonical_end"),
        ("canonical_char_start", "canonical_char_end"),
        ("start_char_idx", "end_char_idx"),
        ("chunk_start", "chunk_end"),
    ):
        for source in (item, metadata, extension):
            start = _optional_int(source.get(start_key))
            end = _optional_int(source.get(end_key))
            if start is not None and end is not None and end >= start:
                return start, end
    if record_start is not None and record_end is not None:
        return record_start, record_end
    return None, None


def _stable_source_name(item: dict[str, Any]) -> str:
    for mapping in _item_mappings(item):
        for key in ("document_id", "evaluation_source_id", "source_name", "file_name"):
            value = str(mapping.get(key) or "").strip()
            if value:
                return value
    return ""


def _source_text(item: dict[str, Any]) -> str:
    for mapping in _item_mappings(item):
        for key in ("file_path", "document_path", "source_path"):
            value = str(mapping.get(key) or "").strip()
            if value:
                return _read_text(value)
    return ""


def _item_mappings(item: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    mappings = [item]
    for key in ("metadata", "extension_metadata"):
        value = item.get(key)
        if isinstance(value, dict):
            mappings.append(value)
    return tuple(mappings)


@lru_cache(maxsize=256)
def _read_text(value: str) -> str:
    path = Path(value)
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _unique_contiguous_match(text: str, quote: str) -> tuple[int, int] | None:
    matches = _contiguous_matches(text, quote)
    return matches[0] if len(matches) == 1 else None


def _contiguous_matches(text: str, quote: str) -> list[tuple[int, int]]:
    parts = str(quote or "").strip().split()
    if not parts or not text:
        return []
    pattern = re.compile(
        r"\s+".join(re.escape(part) for part in parts),
        flags=re.IGNORECASE,
    )
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def _normalized_text_hash(text: str) -> str:
    normalized = " ".join(str(text or "").casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
