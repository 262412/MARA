from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

from scripts.slurm.qasper_debug_contract_natural_payloads import (
    natural_quality_payload_fixture,
)
from scripts.slurm.qasper_debug_contract_probe_cases import (
    NATURAL_QUALITY_PRE_AUDIT_CASES,
)

_FIXTURE_BY_CASE = {
    case.case_id: case.payload_fixture for case in NATURAL_QUALITY_PRE_AUDIT_CASES
}


class ControlledPreAuditProvider:
    """Return controlled invalid proposal payloads without calling an auditor."""

    controlled_pre_audit = True

    def __init__(self, fixture_id: str) -> None:
        self.fixture_id = fixture_id
        self._candidate = ""

    def __call__(self, messages: object, **kwargs: object) -> Any:
        response_format = kwargs.get("response_format")
        response_format = response_format if isinstance(response_format, dict) else {}
        schema = response_format.get("json_schema")
        if not isinstance(schema, dict):
            raise RuntimeError("controlled pre-audit response schema missing")
        name = str(schema.get("name") or "")
        payload: dict[str, object]
        if name == "qasper_typed_candidate":
            payload = {"candidate": self._candidate_from_messages(messages, schema)}
        elif name == "semantic_evidence_set_proposition":
            payload = self._proposal_from_messages(messages, schema)
        else:
            raise RuntimeError(
                f"controlled pre-audit attempted forbidden provider stage {name!r}"
            )
        return SimpleNamespace(
            text=json.dumps(payload, separators=(",", ":")),
            additional_kwargs={"finish_reason": "stop"},
        )

    def _candidate_from_messages(
        self,
        messages: object,
        schema: dict[str, object],
    ) -> str:
        text = _message_text(messages)
        allowed = _candidate_enum(schema)
        controlled = _line_after_optional_marker(
            text,
            "CONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:",
        )
        if controlled:
            candidate = controlled
        else:
            match = re.search(r'"polarity_signal"\s*:\s*"([^"]+)"', text)
            signal = match.group(1).casefold() if match else ""
            candidate = {
                "support": "yes",
                "explicit_contradiction": "no",
                "undetermined": "unanswerable",
            }.get(signal, "")
        if candidate not in allowed:
            raise RuntimeError("controlled pre-audit candidate violates schema")
        self._candidate = candidate
        return candidate

    def _proposal_from_messages(
        self,
        messages: object,
        schema: dict[str, object],
    ) -> dict[str, object]:
        text = _message_text(messages)
        candidate = _required_line_after_marker(
            text,
            "STRUCTURED CANDIDATE TO VERIFY:",
        )
        if not self._candidate or candidate != self._candidate:
            raise RuntimeError("controlled pre-audit candidate identity mismatch")
        match = re.search(r"(?m)^\[(E\d+:S\d+)\]\s+([^\n]+)", text)
        if not match:
            raise RuntimeError("controlled pre-audit evidence span missing")
        return natural_quality_payload_fixture(
            self.fixture_id,
            schema,
            candidate=candidate,
            selector=match.group(1),
            evidence_text=match.group(2).strip(),
        )


def controlled_pre_audit_model_factory(
    *,
    case_id: str,
    **_: object,
) -> ControlledPreAuditProvider:
    fixture_id = _FIXTURE_BY_CASE.get(case_id)
    if not fixture_id:
        raise RuntimeError(f"controlled pre-audit fixture missing for {case_id}")
    return ControlledPreAuditProvider(fixture_id)


def _message_text(messages: object) -> str:
    if not isinstance(messages, (list, tuple)) or not messages:
        raise RuntimeError("controlled pre-audit message stack missing")
    values: list[str] = []
    for message in messages:
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("controlled pre-audit message content missing")
        values.append(content)
    return "\n\n".join(values)


def _candidate_enum(schema: dict[str, object]) -> set[str]:
    body = schema.get("schema")
    body = body if isinstance(body, dict) else {}
    properties = body.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    candidate = properties.get("candidate")
    candidate = candidate if isinstance(candidate, dict) else {}
    values = candidate.get("enum")
    return {str(value) for value in values} if isinstance(values, list) else set()


def _line_after_optional_marker(text: str, marker: str) -> str:
    position = text.find(marker)
    if position < 0:
        return ""
    return text[position + len(marker) :].strip().split(maxsplit=1)[0].casefold()


def _required_line_after_marker(text: str, marker: str) -> str:
    value = _line_after_optional_marker(text, marker)
    if not value:
        raise RuntimeError(f"controlled pre-audit marker missing: {marker}")
    return value
