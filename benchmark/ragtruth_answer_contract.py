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
    candidates = [
        value for value in _json_candidates(answer) if value.lstrip().startswith("{")
    ]
    for candidate in candidates:
        repaired_json = _repair_json_control_characters(candidate)
        try:
            parsed = json.loads(repaired_json)
        except json.JSONDecodeError:
            parsed = None
        if _valid_ragtruth_json(parsed):
            return json.dumps(parsed, ensure_ascii=False), True, True
        try:
            parsed = ast.literal_eval(candidate)
        except (SyntaxError, ValueError):
            continue
        if _valid_ragtruth_json(parsed):
            return json.dumps(parsed, ensure_ascii=False), True, True
    return "", True, False


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
    candidates.extend(_embedded_json_objects(text))
    candidates.extend(_balanced_braced_objects(text))
    return [candidate for candidate in candidates if candidate]


def _embedded_json_objects(text: str) -> list[str]:
    decoder = json.JSONDecoder()
    candidates: list[str] = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        candidates.append(text[index : index + end])
    return candidates


def _balanced_braced_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if in_string and character == "\\":
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None
    return candidates


def _repair_json_control_characters(candidate: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    replacements = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for character in candidate:
        if in_string and character in replacements:
            output.append(replacements[character])
            escaped = False
            continue
        output.append(character)
        if escaped:
            escaped = False
            continue
        if in_string and character == "\\":
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
    return "".join(output)
