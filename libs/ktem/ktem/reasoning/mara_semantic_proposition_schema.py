from __future__ import annotations

import json
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)


def semantic_proposition_response_format(
    labels: list[str],
    slot_ids: list[str],
) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "semantic_evidence_set_proposition",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": ["yes", "no", "insufficient_evidence"],
                    },
                    "support_mode": {"type": "string", "enum": ["evidence_set"]},
                    "jointly_complete": {"type": "boolean"},
                    "each_premise_required": {"type": "boolean"},
                    "premises": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_ref": {"type": "string", "enum": labels},
                                "quote": {"type": "string", "maxLength": 640},
                                "proposition_fragment": {
                                    "type": "string",
                                    "maxLength": 320,
                                },
                                "supports_slot_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "enum": slot_ids},
                                },
                            },
                            "required": [
                                "evidence_ref",
                                "quote",
                                "proposition_fragment",
                                "supports_slot_ids",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "verdict",
                    "support_mode",
                    "jointly_complete",
                    "each_premise_required",
                    "premises",
                ],
                "additionalProperties": False,
            },
        },
    }


def parse_semantic_proposition_result(
    response_text: str,
    *,
    packed: list[dict[str, str]],
    slot_ids: set[str],
    model: str,
    seed: int,
) -> dict[str, Any] | None:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {
        "verdict",
        "support_mode",
        "jointly_complete",
        "each_premise_required",
        "premises",
    }:
        return None
    verdict = payload.get("verdict")
    if verdict not in {"yes", "no", "insufficient_evidence"}:
        return None
    if payload.get("support_mode") != "evidence_set":
        return None
    if not isinstance(payload.get("jointly_complete"), bool) or not isinstance(
        payload.get("each_premise_required"), bool
    ):
        return None
    raw_premises = payload.get("premises")
    if not isinstance(raw_premises, list) or len(raw_premises) > 4:
        return None
    if verdict in {"yes", "no"} and (
        not 2 <= len(raw_premises) <= 4
        or payload["jointly_complete"] is not True
        or payload["each_premise_required"] is not True
    ):
        return None
    if verdict == "insufficient_evidence" and (
        raw_premises
        or payload["jointly_complete"] is not False
        or payload["each_premise_required"] is not False
    ):
        return None
    label_to_id = {value["label"]: value["evidence_id"] for value in packed}
    premises = _parse_premises(raw_premises, label_to_id, slot_ids)
    if premises is None:
        return None
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": verdict,
        "support_mode": "evidence_set",
        "jointly_complete": payload["jointly_complete"],
        "each_premise_required": payload["each_premise_required"],
        "premises": premises,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }


def _parse_premises(
    raw_premises: list[Any],
    label_to_id: dict[str, str],
    slot_ids: set[str],
) -> list[dict[str, Any]] | None:
    premises: list[dict[str, Any]] = []
    for raw in raw_premises:
        if not isinstance(raw, dict) or set(raw) != {
            "evidence_ref",
            "quote",
            "proposition_fragment",
            "supports_slot_ids",
        }:
            return None
        evidence_id = label_to_id.get(str(raw.get("evidence_ref") or ""))
        quote = raw.get("quote")
        fragment = raw.get("proposition_fragment")
        supports = raw.get("supports_slot_ids")
        if (
            not evidence_id
            or not isinstance(quote, str)
            or not isinstance(fragment, str)
            or not isinstance(supports, list)
            or not supports
            or any(
                not isinstance(value, str) or value not in slot_ids
                for value in supports
            )
            or len(set(supports)) != len(supports)
        ):
            return None
        premises.append(
            {
                "evidence_id": evidence_id,
                "quote": quote,
                "proposition_fragment": fragment,
                "supports_slot_ids": list(supports),
            }
        )
    premise_spans = {(value["evidence_id"], value["quote"]) for value in premises}
    return premises if len(premise_spans) == len(premises) else None
