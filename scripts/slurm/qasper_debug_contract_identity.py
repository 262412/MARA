from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.slurm.qasper_debug_contract_support import (
    _QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
)


def _raw_candidate_fields_present(generator: dict[str, Any]) -> bool:
    required = {
        "raw_response",
        "raw_response_digest",
        "provider_output_digest",
        "raw_response_truncated",
        "cleaned_response",
        "raw_candidate",
        "raw_candidate_digest",
        "typed_candidate",
        "typed_candidate_digest",
        "raw_candidate_identity_preserved",
        "output_digest",
    }
    return required <= set(generator)


def _raw_candidate_identity_valid(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    parts = _raw_candidate_parts(generator)
    return bool(
        parts
        and _raw_candidate_fields_valid(generator, parts)
        and _raw_candidate_stages_valid(generator, parts)
        and _raw_candidate_output_valid(generator, parts)
        and _raw_candidate_attempt_valid(generator, parts)
        and _controlled_candidate_transport_identity_valid(generator, verifier)
        and _verifier_raw_identity_valid(verifier, parts)
    )


def _controlled_candidate_transport_identity_valid(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    requested = _normalized_candidate(
        generator.get("requested_controlled_candidate")
        or generator.get("controlled_original_candidate")
    )
    if not requested:
        return True
    values = (
        _normalized_candidate(generator.get("provider_raw_candidate")),
        _normalized_candidate(generator.get("cleaned_candidate")),
        _normalized_candidate(generator.get("typed_candidate")),
        _normalized_candidate(generator.get("verifier_input_candidate")),
        _normalized_candidate(verifier.get("candidate_label")),
    )
    return bool(
        requested in {"yes", "no", "unanswerable"}
        and generator.get("candidate_transport_contract_id")
        == "qasper_candidate_transport_identity.v1"
        and all(value == requested for value in values)
        and generator.get("candidate_transport_identity_preserved") is True
        and generator.get("candidate_transport_status") == "passed"
    )


def _raw_candidate_parts(generator: dict[str, Any]) -> dict[str, Any]:
    if not _raw_candidate_fields_present(generator):
        return {}
    raw = generator.get("raw_response")
    if (
        not isinstance(raw, str)
        or not raw
        or generator.get("raw_response_truncated") is not False
        or len(raw) > _QASPER_CANDIDATE_MAX_RESPONSE_CHARS
    ):
        return {}
    bounded = raw[:_QASPER_CANDIDATE_MAX_RESPONSE_CHARS]
    cleaned = bounded.strip()
    raw_candidate = _parse_candidate_response(bounded)
    candidate = _normalized_candidate(generator.get("typed_candidate"))
    if not raw_candidate or raw_candidate != _parse_candidate_response(cleaned):
        return {}
    if candidate != raw_candidate or generator.get("raw_candidate") != raw_candidate:
        return {}
    return {
        "raw": raw,
        "bounded": bounded,
        "cleaned": cleaned,
        "candidate": candidate,
        "raw_candidate": raw_candidate,
    }


def _raw_candidate_fields_valid(
    generator: dict[str, Any],
    parts: dict[str, Any],
) -> bool:
    raw = parts["raw"]
    bounded = parts["bounded"]
    cleaned = parts["cleaned"]
    raw_candidate = parts["raw_candidate"]
    candidate = parts["candidate"]
    return bool(
        generator.get("raw_candidate_identity_preserved") is True
        and generator.get("raw_candidate_failure_reason") in {None, ""}
        and generator.get("failure_reason") in {None, ""}
        and generator.get("raw_response_digest") == _digest(bounded)
        and generator.get("provider_output_digest") == _digest(raw)
        and generator.get("cleaned_response") == cleaned
        and generator.get("raw_candidate_digest") == _digest(raw_candidate)
        and generator.get("typed_candidate_digest") == _digest(candidate)
    )


def _raw_candidate_stages_valid(
    generator: dict[str, Any],
    parts: dict[str, Any],
) -> bool:
    stages = generator.get("transformation_stages")
    stages = stages if isinstance(stages, list) else []
    names = [
        str(stage.get("stage") or "") for stage in stages if isinstance(stage, dict)
    ]
    if (
        len(stages) != 3
        or len(names) != 3
        or set(names)
        != {
            "raw_response",
            "cleaning",
            "typed_candidate",
        }
    ):
        return False
    by_name = {
        str(stage.get("stage") or ""): stage
        for stage in stages
        if isinstance(stage, dict)
    }
    raw_stage = by_name.get("raw_response") or {}
    cleaning_stage = by_name.get("cleaning") or {}
    typed_stage = by_name.get("typed_candidate") or {}
    bounded = parts["bounded"]
    cleaned = parts["cleaned"]
    candidate = parts["candidate"]
    return bool(
        raw_stage.get("value") == bounded
        and raw_stage.get("digest") == _digest(bounded)
        and cleaning_stage.get("value") == cleaned
        and cleaning_stage.get("digest") == _digest(cleaned)
        and cleaning_stage.get("changed") is (bounded != cleaned)
        and typed_stage.get("value") == candidate
        and typed_stage.get("digest") == _digest(candidate)
        and typed_stage.get("source_stage") == "cleaning"
        and typed_stage.get("identity_preserved") is True
    )


def _raw_candidate_output_valid(
    generator: dict[str, Any],
    parts: dict[str, Any],
) -> bool:
    bounded = parts["bounded"]
    raw = parts["raw"]
    cleaned = parts["cleaned"]
    raw_candidate = parts["raw_candidate"]
    candidate = parts["candidate"]
    expected = {
        "raw_response_digest": _digest(bounded),
        "provider_output_digest": _digest(raw),
        "cleaned_response_digest": _digest(cleaned),
        "raw_candidate": raw_candidate,
        "raw_candidate_digest": _digest(raw_candidate),
        "typed_candidate": candidate,
        "typed_candidate_digest": _digest(candidate),
        "raw_candidate_identity_preserved": True,
        "status": "parsed",
        "failure_reason": generator.get("failure_reason") or "",
        "finish_reason": generator.get("finish_reason") or "",
    }
    return generator.get("output_digest") == _digest(expected)


def _raw_candidate_attempt_valid(
    generator: dict[str, Any],
    parts: dict[str, Any],
) -> bool:
    attempts = generator.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return False
    attempt = attempts[-1] if isinstance(attempts[-1], dict) else {}
    expected = {
        "attempt_id": generator.get("attempt_id"),
        "status": "parsed",
        "raw_response": parts["bounded"],
        "cleaned_response": parts["cleaned"],
        "raw_candidate": parts["raw_candidate"],
        "raw_candidate_digest": _digest(parts["raw_candidate"]),
        "typed_candidate": parts["candidate"],
        "typed_candidate_digest": _digest(parts["candidate"]),
        "raw_candidate_identity_preserved": True,
        "finish_reason": generator.get("finish_reason"),
        "output_digest": generator.get("output_digest"),
    }
    return all(attempt.get(field) == value for field, value in expected.items())


def _verifier_raw_identity_valid(
    verifier: dict[str, Any],
    parts: dict[str, Any],
) -> bool:
    candidate = parts["candidate"]
    raw_candidate = parts["raw_candidate"]
    return bool(
        _normalized_candidate(verifier.get("candidate_label")) == candidate
        and verifier.get("raw_candidate_digest") == _digest(raw_candidate)
        and verifier.get("typed_candidate_digest") == _digest(candidate)
        and verifier.get("verifier_input_candidate_digest") == _digest(candidate)
        and verifier.get("candidate_raw_identity_preserved") is True
    )


def _parse_candidate_response(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict) or set(payload) != {"candidate"}:
        return ""
    candidate = _normalized_candidate(payload.get("candidate"))
    return candidate if candidate in {"yes", "no", "unanswerable"} else ""


def _normalized_candidate(value: Any) -> str:
    return str(value or "").strip().casefold()


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
