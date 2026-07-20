from __future__ import annotations

import ast
import json
import re
from typing import Any

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def ragtruth_json_answer(answer: str) -> tuple[str, bool, bool]:
    strict = _extract_json_answer(answer)
    if strict:
        return strict, False, False
    candidate = next(
        (value for value in _json_candidates(answer) if value.lstrip().startswith("{")),
        "",
    )
    if not candidate:
        return "", True, False
    try:
        parsed = ast.literal_eval(candidate)
    except (SyntaxError, ValueError):
        return "", True, False
    if not _valid_ragtruth_json(parsed):
        return "", True, False
    return json.dumps(parsed, ensure_ascii=False), True, True


def ragtruth_finalization_metadata(answer: str) -> dict[str, Any]:
    parsed, repair_attempted, repair_succeeded = ragtruth_json_answer(answer)
    return {
        "ragtruth_json_repair_attempted": repair_attempted,
        "ragtruth_json_repair_succeeded": repair_succeeded,
        "ragtruth_json_valid": bool(parsed),
        "task_contract_status": "ok" if parsed else "error",
    }


def _extract_json_answer(answer: str) -> str:
    for candidate in _json_candidates(answer):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if _valid_ragtruth_json(parsed):
            return json.dumps(parsed, ensure_ascii=False)
    return ""


def _valid_ragtruth_json(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"hallucination list"}:
        return False
    spans = value.get("hallucination list")
    return isinstance(spans, list) and all(isinstance(span, str) for span in spans)


def _json_candidates(answer: str) -> list[str]:
    text = str(answer or "").strip()
    candidates = [match.group(1).strip() for match in _JSON_BLOCK_RE.finditer(text)]
    candidates.append(text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if 0 <= first_brace < last_brace:
        candidates.append(text[first_brace : last_brace + 1])
    return [candidate for candidate in candidates if candidate]
