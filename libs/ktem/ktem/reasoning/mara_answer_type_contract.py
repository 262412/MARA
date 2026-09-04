from __future__ import annotations

import re
from typing import Any


def message_with_answer_type_contract(message: str, request: Any) -> str:
    answer_type = request_answer_type(request)
    if not answer_type or "Required answer type:" in str(message or ""):
        return str(message or "")
    requirements = {
        "boolean": (
            "Answer yes or no only when the selected evidence supports the "
            "complete proposition; otherwise answer unanswerable."
        ),
        "free_text": (
            "Answer in concise prose grounded in the selected evidence. Do not "
            "use a numeric or formula template unless the question asks for one."
        ),
        "numeric": (
            "Return the verified numeric result and preserve its unit and scale."
        ),
    }
    instruction = requirements.get(answer_type)
    if not instruction:
        return str(message or "")
    return (
        f"{str(message or '').rstrip()}\n\nBenchmark answer contract:\n"
        f"- Required answer type: {answer_type}.\n"
        f"- {instruction}"
    )


def request_answer_type(request: Any) -> str:
    plan = getattr(request, "query_plan", None)
    if plan is not None and hasattr(plan, "answer_type"):
        return str(plan.answer_type or "").strip().lower()
    if isinstance(plan, dict):
        return str(plan.get("answer_type") or "").strip().lower()
    return (
        str(
            getattr(request, "answer_type", None)
            or getattr(request, "task_type", None)
            or ""
        )
        .strip()
        .lower()
    )


def answer_type_consistency(answer_type: str, answer: str) -> tuple[bool, str]:
    normalized = " ".join(str(answer or "").strip().lower().split())
    if not normalized:
        return False, "empty_answer"
    if normalized.startswith(
        (
            "mara could not retrieve enough evidence",
            "unanswerable",
            "insufficient evidence",
        )
    ):
        return True, "abstention"
    if answer_type == "boolean":
        consistent = normalized.split(maxsplit=1)[0].rstrip(".:") in {
            "yes",
            "no",
            "true",
            "false",
        }
        return consistent, "boolean_polarity" if consistent else "non_boolean_answer"
    if answer_type == "numeric":
        consistent = any(character.isdigit() for character in normalized)
        return consistent, "numeric_value" if consistent else "missing_numeric_value"
    if answer_type == "free_text":
        words = re.findall(r"[a-z\u3400-\u9fff]+", normalized)
        formula_only = normalized.startswith(("=", "$$", "\\[")) and len(words) < 3
        return not formula_only, (
            "formula_only_answer" if formula_only else "free_text"
        )
    return True, "not_constrained"
