from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast

from ktem.docqa.evidence_identity import exact_evidence_aliases

from .qasper_evidence_identity import canonical_evidence_identity

ROW_CONTRACT_ID = "qasper_golden_replay.row.v1"
REQUIRED_ROW_FIELDS = (
    "contract_id",
    "run_label",
    "example_id",
    "route",
    "raw_question",
    "actual_retrieval_query",
    "candidate_evidence_identities",
    "reranker_input_identities",
    "reranker_output_identities",
    "selected_evidence_identities",
    "required_slot_states",
    "typed_authority",
    "verifier_decision",
    "guardrail_decision",
    "semantic_answer",
    "presentation_answer",
    "answer_status",
    "raw_terminal_outcome",
    "raw_terminal_outcome_reason",
    "terminal_outcome",
    "terminal_outcome_reason",
    "terminal_outcome_provenance",
    "control_counts",
    "verifier_observability",
    "native_score",
    "source_projection_hashes",
)


@dataclass(frozen=True)
class _EvidenceIndex:
    alias_to_identity: dict[str, str]
    runtime_source_to_stable_source: dict[str, str]

    @classmethod
    def from_prediction(cls, prediction: dict[str, Any]) -> _EvidenceIndex:
        aliases: dict[str, str] = {}
        sources: dict[str, str] = {}
        for item in _all_evidence_items(prediction):
            identity = _canonical_evidence_key(item)
            stable_source = identity.split("|", maxsplit=1)[0]
            for alias in _item_aliases(item):
                aliases.setdefault(alias, identity)
            for source in _runtime_source_aliases(item):
                sources.setdefault(source, stable_source)
        return cls(aliases, sources)

    def normalize_reference(self, value: Any) -> Any:
        if not isinstance(value, str) or not value:
            return value
        direct = self.alias_to_identity.get(value)
        if direct:
            return direct
        base, marker, suffix = value.partition("#")
        normalized_base = self.alias_to_identity.get(base)
        if normalized_base:
            return f"{normalized_base}{marker}{suffix}" if marker else normalized_base
        return self.runtime_source_to_stable_source.get(value, value)


def project_prediction(
    prediction: dict[str, Any],
    *,
    run_label: str,
    allowed_run_labels: tuple[str, ...],
) -> dict[str, Any]:
    if run_label not in allowed_run_labels:
        raise ValueError(f"Unknown golden replay run label: {run_label}")
    metadata = _mapping(prediction.get("evidence_metadata"))
    terminal = _mapping(prediction.get("terminal_semantic_commit"))
    evidence_index = _EvidenceIndex.from_prediction(prediction)
    observability = _mapping(prediction.get("verifier_observability"))
    verifier = _mapping(
        prediction.get("engine_verify_decision") or prediction.get("verify_decision")
    )
    guardrail = _mapping(
        prediction.get("guardrail_decision")
        or prediction.get("engine_terminal_guardrail_decision")
    )
    return {
        "contract_id": ROW_CONTRACT_ID,
        "run_label": run_label,
        "example_id": str(prediction.get("example_id") or ""),
        "route": str(prediction.get("route") or ""),
        "raw_question": str(
            prediction.get("benchmark_question") or prediction.get("question") or ""
        ),
        "actual_retrieval_query": str(
            prediction.get("benchmark_retrieval_query") or ""
        ),
        "candidate_evidence_identities": _evidence_identities(
            metadata.get("candidate_evidence")
        ),
        "reranker_input_identities": _evidence_identities(
            metadata.get("reranker_input_evidence")
        ),
        "reranker_output_identities": _evidence_identities(
            metadata.get("reranked_evidence")
        ),
        "selected_evidence_identities": _evidence_identities(
            metadata.get("selected_evidence")
        ),
        "required_slot_states": _required_slot_states(metadata, evidence_index),
        "typed_authority": _typed_authority_projection(
            metadata,
            verifier,
            evidence_index,
        ),
        "verifier_decision": _verifier_projection(verifier, evidence_index),
        "guardrail_decision": _normalize_value(guardrail, evidence_index),
        **_answer_projection(prediction, terminal),
        "control_counts": _control_counts(observability),
        "verifier_observability": _observability_projection(observability),
        "native_score": _mapping(prediction.get("metrics")).get("native_score"),
        "source_projection_hashes": {
            "engine_terminal": _optional_text(
                prediction.get("engine_terminal_projection_hash")
            ),
            "terminal_commit": _optional_text(terminal.get("projection_hash")),
        },
    }


def _answer_projection(
    prediction: dict[str, Any],
    terminal: dict[str, Any],
) -> dict[str, Any]:
    answer_status = str(
        terminal.get("answer_status") or prediction.get("answer_status") or ""
    )
    raw_outcome = _optional_text(
        prediction.get("terminal_outcome") or terminal.get("outcome")
    )
    raw_reason = _optional_text(
        prediction.get("terminal_outcome_reason") or terminal.get("outcome_reason")
    )
    outcome, reason, provenance = _normalized_terminal_outcome(
        prediction,
        answer_status=answer_status,
        raw_outcome=raw_outcome,
        raw_reason=raw_reason,
    )
    return {
        "semantic_answer": str(
            terminal.get("semantic_answer")
            or prediction.get("answer_for_scoring")
            or prediction.get("predicted_answer")
            or ""
        ),
        "presentation_answer": str(
            terminal.get("presentation_answer")
            or prediction.get("answer_for_user")
            or prediction.get("predicted_answer")
            or ""
        ),
        "answer_status": answer_status,
        "raw_terminal_outcome": raw_outcome,
        "raw_terminal_outcome_reason": raw_reason,
        "terminal_outcome": outcome,
        "terminal_outcome_reason": reason,
        "terminal_outcome_provenance": provenance,
    }


def _normalized_terminal_outcome(
    prediction: dict[str, Any],
    *,
    answer_status: str,
    raw_outcome: str | None,
    raw_reason: str | None,
) -> tuple[str | None, str | None, str]:
    if raw_outcome:
        return raw_outcome, raw_reason, "artifact"
    error = str(prediction.get("error") or "").strip().casefold()
    if "timeout" in error or "timed out" in error:
        return "timeout", "legacy_error_timeout", "legacy_derived"
    if "cancel" in error:
        return "cancelled", "legacy_error_cancelled", "legacy_derived"
    if error:
        return "execution_failed", "legacy_error", "legacy_derived"
    if answer_status == "answered":
        return "answered", "legacy_answer_status_answered", "legacy_derived"
    if answer_status == "abstained":
        return "safe_abstention", "legacy_answer_status_abstained", "legacy_derived"
    return None, None, "unclassified"


def _typed_authority_projection(
    metadata: dict[str, Any],
    verifier: dict[str, Any],
    evidence_index: _EvidenceIndex,
) -> dict[str, Any]:
    authority = _mapping(
        metadata.get("typed_authority")
        or verifier.get("typed_authority")
        or metadata.get("boolean_authority")
    )
    normalized = _normalize_value(authority, evidence_index)
    atoms = [
        _authority_atom_projection(raw_atom, evidence_index)
        for raw_atom in authority.get("authority_atoms") or []
        if isinstance(raw_atom, dict)
    ]
    projection = {
        "contract_id": str(authority.get("contract_id") or ""),
        "state": str(
            authority.get("state")
            or authority.get("status")
            or verifier.get("boolean_authority_status")
            or ""
        ),
        "reason": str(authority.get("reason") or ""),
        "answer_type": str(authority.get("answer_type") or ""),
        "canonical_answer_polarity": str(
            authority.get("canonical_answer_polarity")
            or verifier.get("canonical_answer_polarity")
            or ""
        ),
        "required_slot_ids": _text_list(authority.get("required_slot_ids")),
        "verified_slot_ids": _text_list(authority.get("verified_slot_ids")),
        "slot_bindings": _normalize_value(
            _mapping(authority.get("slot_bindings")), evidence_index
        ),
        "authority_atoms": atoms,
        "normalized_sha256": _stable_hash(normalized),
    }
    if isinstance(authority.get("slot_ref_bindings"), dict):
        projection["slot_ref_bindings"] = _normalize_value(
            _mapping(authority.get("slot_ref_bindings")), evidence_index
        )
    return projection


def _authority_atom_projection(
    atom: dict[str, Any],
    evidence_index: _EvidenceIndex,
) -> dict[str, Any]:
    return {
        "evidence_identity": evidence_index.normalize_reference(
            atom.get("evidence_id")
        ),
        "evidence_ref": evidence_index.normalize_reference(atom.get("evidence_ref")),
        "quote_sha256": _text_hash(atom.get("quote")),
        "span_start": atom.get("span_start"),
        "span_end": atom.get("span_end"),
        "canonical_start": atom.get("canonical_start"),
        "canonical_end": atom.get("canonical_end"),
        **{
            key: atom.get(key)
            for key in (
                "actor",
                "relation",
                "predicate",
                "object",
                "arguments",
                "polarity",
                "qualifier",
                "quantifier",
                "scope",
                "section_scope",
                "reason",
            )
        },
    }


def _verifier_projection(
    verifier: dict[str, Any],
    evidence_index: _EvidenceIndex,
) -> dict[str, Any]:
    normalized = _normalize_value(verifier, evidence_index)
    projection = {
        key: verifier.get(key)
        for key in (
            "mode",
            "status",
            "reason",
            "action",
            "input_answer_polarity",
            "canonical_answer_polarity",
            "semantic_correction_applied",
            "boolean_authority_status",
            "actor",
            "relation",
            "object",
            "predicate",
            "arguments",
            "qualifier",
            "quantifier",
            "scope",
            "section_scope",
            "verified_support_slot_ids",
        )
    }
    projection.update(
        {
            "authoritative_evidence_identity": evidence_index.normalize_reference(
                verifier.get("authoritative_evidence_id")
            ),
            "authoritative_evidence_ref": evidence_index.normalize_reference(
                verifier.get("authoritative_evidence_ref")
            ),
            "authoritative_quote_sha256": _text_hash(
                verifier.get("authoritative_quote")
            ),
            "authoritative_conflict": _normalize_value(
                verifier.get("authoritative_conflict") or {}, evidence_index
            ),
            "normalized_sha256": _stable_hash(normalized),
        }
    )
    return projection


def _required_slot_states(
    metadata: dict[str, Any],
    evidence_index: _EvidenceIndex,
) -> list[dict[str, Any]]:
    states = [
        cast(dict[str, Any], _normalize_value(raw_state, evidence_index))
        for raw_state in metadata.get("verification_slot_states") or []
        if isinstance(raw_state, dict)
    ]
    return sorted(states, key=_canonical_json)


def _control_counts(observability: dict[str, Any]) -> dict[str, int]:
    return {
        key: _integer(observability.get(key))
        for key in (
            "retrieval_retry_count",
            "retry_count",
            "route_switch_count",
            "verifier_recovery_count",
        )
    }


def _observability_projection(observability: dict[str, Any]) -> dict[str, int]:
    return {
        key: _integer(observability.get(key))
        for key in (
            "abstained",
            "true_abstention",
            "false_abstention",
            "unsupported_claim_count",
            "has_unsupported_claim",
        )
    }


def _all_evidence_items(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items = _dict_items(prediction.get("retrieved_hits"))
    metadata = _mapping(prediction.get("evidence_metadata"))
    for key, value in metadata.items():
        if key.endswith("_evidence") or key in {"evidence", "candidate_evidence"}:
            items.extend(_dict_items(value))
    return items


def _evidence_identities(value: Any) -> list[str]:
    return [_canonical_evidence_key(item) for item in _dict_items(value)]


def _canonical_evidence_key(item: dict[str, Any]) -> str:
    identity = canonical_evidence_identity(item, text=_item_text(item))
    page = _first_text(item, "dataset_page", "page_label")
    return "|".join(
        (
            identity.source_id,
            page,
            "" if identity.chunk_start is None else str(identity.chunk_start),
            "" if identity.chunk_end is None else str(identity.chunk_end),
            identity.text_hash,
        )
    )


def _item_aliases(item: dict[str, Any]) -> set[str]:
    aliases = set()
    try:
        aliases.update(exact_evidence_aliases(item))
    except ValueError:
        pass
    for mapping in _item_mappings(item):
        for key in (
            "evidence_id",
            "canonical_id",
            "identity",
            "evaluation_identity",
            "runtime_identity",
        ):
            value = str(mapping.get(key) or "").strip()
            if value:
                aliases.add(value)
    return aliases


def _runtime_source_aliases(item: dict[str, Any]) -> set[str]:
    aliases = set()
    for mapping in _item_mappings(item):
        for key in ("source_id", "runtime_source_id", "file_id"):
            value = str(mapping.get(key) or "").strip()
            if value:
                aliases.add(value)
    return aliases


def _item_mappings(item: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    mappings = [item]
    for key in ("metadata", "extension_metadata"):
        value = item.get(key)
        if isinstance(value, dict):
            mappings.append(value)
    return tuple(mappings)


def _normalize_value(value: Any, evidence_index: _EvidenceIndex) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(child, evidence_index)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(child, evidence_index) for child in value]
    return evidence_index.normalize_reference(value)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _text_hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for mapping in _item_mappings(item):
        for key in keys:
            value = str(mapping.get(key) or "").strip()
            if value:
                return value
    return ""


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], item) for item in value or [] if isinstance(item, dict)
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _text_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if str(item)]


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
