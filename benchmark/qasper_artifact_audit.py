"""Read-only audits for QASPER prediction artifacts.

The benchmark runner scores the final terminal state, while the answerability
contract trace preserves the engine answer that entered the contract.  This
module keeps those two stages separate for artifact review without importing
or invoking runtime code.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .jsonl import read_jsonl
from .metrics import is_abstention_answer

_FIELD_PATHS = {
    "engine_product_answer": (
        "evidence_metadata.answerability_contract_trace.product_answer"
    ),
    "engine_pre_contract_answer": (
        "evidence_metadata.answerability_contract_trace.pre_contract_answer"
    ),
    "engine_pre_contract_verification": (
        "evidence_metadata.answerability_contract_trace.pre_contract_verification"
    ),
    "engine_pre_guardrail_answer": (
        "evidence_metadata.answerability_contract_trace.pre_guardrail_answer"
    ),
    "engine_pre_verification_answer": (
        "evidence_metadata.answerability_contract_trace.pre_verification_answer"
    ),
    "contract_candidate_answer": (
        "evidence_metadata.answerability_contract_trace.candidate_for_answerability"
    ),
    "contract_post_answer": (
        "evidence_metadata.answerability_contract_trace.post_contract_answer"
    ),
    "contract_final_post_answer": (
        "evidence_metadata.answerability_contract_trace.final_post_contract_answer"
    ),
    "contract_rewrite_type": (
        "evidence_metadata.answerability_contract_trace.rewrite_type"
    ),
    "final_terminal_answer": "terminal_answer_state.answer",
    "final_terminal_status": "terminal_answer_state.answer_status",
}


def audit_qasper_predictions(
    predictions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a route and contract audit without mutating prediction rows."""

    rows = [dict(prediction) for prediction in predictions]
    route_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        route_rows[_route(row)].append(row)

    routes = {route: _route_audit(route_rows[route]) for route in sorted(route_rows)}
    matrix = _transformation_matrix(rows)
    return {
        "rows": len(rows),
        "routes": routes,
        "totals": _route_totals(routes),
        "distinct_false_abstention_entering_contract_with_polarity_count": len(
            {
                _example_id(row)
                for row in rows
                if _false_abstention_entering_with_polarity(row)
            }
        ),
        "schema_gaps": _schema_gaps(rows),
        "route_differences": {
            "engine_product_answer": _route_difference_count(
                rows, _engine_product_answer
            ),
            "post_contract_answer": _route_difference_count(
                rows, _contract_post_answer
            ),
            "final_answer": _route_difference_count(rows, _final_answer),
        },
        "transformation_matrix": matrix,
        "field_paths": dict(_FIELD_PATHS),
    }


def audit_qasper_predictions_file(path: str | Path) -> dict[str, Any]:
    """Read one predictions JSONL file and return :func:`audit_qasper_predictions`."""
    rows: list[dict[str, Any]] = []
    for line_number, value in enumerate(read_jsonl(path), start=1):
        if not isinstance(value, dict):
            raise ValueError(
                f"predictions JSONL record {line_number} must be an object"
            )
        rows.append(value)
    return audit_qasper_predictions(rows)


def _route_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows if _gold_is_answerable(row)]
    product_categories = [_answer_category(_engine_product_answer(row)) for row in rows]
    final_categories = [_answer_category(_final_answer(row)) for row in rows]
    removed = [
        row
        for row in answerable
        if _gold_category(row) in {"Y", "N"}
        and _answer_category(_engine_product_answer(row)) == _gold_category(row)
        and _answer_category(_contract_post_answer(row)) == "U"
    ]
    return {
        "num_predictions": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_gold_count": len(rows) - len(answerable),
        "pre_contract_false_abstention_count": sum(
            _answer_category(_engine_product_answer(row)) == "U" for row in answerable
        ),
        "post_contract_false_abstention_count": sum(
            _answer_category(_contract_post_answer(row)) == "U" for row in answerable
        ),
        "final_false_abstention_count": sum(
            _answer_category(_final_answer(row)) == "U" for row in answerable
        ),
        "correct_product_polarity_removed_count": len(removed),
        "correct_product_polarity_removed_by_value": {
            label: sum(_gold_category(row) == value for row in removed)
            for label, value in (("yes", "Y"), ("no", "N"))
        },
        "false_abstention_entering_contract_with_polarity_count": sum(
            _false_abstention_entering_with_polarity(row) for row in rows
        ),
        "engine_product_answer_counts": _category_counts(product_categories),
        "final_answer_counts": _category_counts(final_categories),
        "engine_product_exact_correct_count": sum(
            _normalized(_engine_product_answer(row)) == _normalized(_gold_answer(row))
            for row in rows
        ),
        "final_exact_correct_count": sum(
            _normalized(_final_answer(row)) == _normalized(_gold_answer(row))
            for row in rows
        ),
    }


def _schema_gaps(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "answerability_trace_missing_count": sum(
            not _answerability_trace(row) for row in rows
        ),
        "engine_product_answer_missing_count": sum(
            not _engine_product_answer(row).strip() for row in rows
        ),
        "contract_post_answer_missing_count": sum(
            not _contract_post_answer(row).strip() for row in rows
        ),
        "top_level_pre_contract_verification_missing_count": sum(
            "pre_contract_verification" not in row for row in rows
        ),
        "trace_pre_contract_verification_missing_count": sum(
            "pre_contract_verification" not in _answerability_trace(row) for row in rows
        ),
        "terminal_answer_state_missing_count": sum(
            "terminal_answer_state" not in row for row in rows
        ),
    }


def _route_totals(routes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    numeric_fields = (
        "num_predictions",
        "answerable_count",
        "unanswerable_gold_count",
        "pre_contract_false_abstention_count",
        "post_contract_false_abstention_count",
        "final_false_abstention_count",
        "correct_product_polarity_removed_count",
        "false_abstention_entering_contract_with_polarity_count",
        "engine_product_exact_correct_count",
        "final_exact_correct_count",
    )
    totals: dict[str, Any] = {
        field: sum(int(route.get(field) or 0) for route in routes.values())
        for field in numeric_fields
    }
    for field in ("engine_product_answer_counts", "final_answer_counts"):
        totals[field] = {
            category: sum(
                int((route.get(field) or {}).get(category) or 0)
                for route in routes.values()
            )
            for category in ("Y", "N", "U", "F")
        }
    totals["correct_product_polarity_removed_by_value"] = {
        label: sum(
            int(
                (route.get("correct_product_polarity_removed_by_value") or {}).get(
                    label
                )
                or 0
            )
            for route in routes.values()
        )
        for label in ("yes", "no")
    }
    return totals


def _transformation_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in rows:
        key = (
            _route(row),
            _answer_category(_engine_product_answer(row)),
            _answer_category(_contract_post_answer(row)),
            _answer_category(_final_answer(row)),
        )
        counts[key] += 1
    return [
        {
            "route": route,
            "engine": engine,
            "contract": contract,
            "final": final,
            "count": counts[(route, engine, contract, final)],
        }
        for route, engine, contract, final in sorted(counts)
    ]


def _route_difference_count(
    rows: list[dict[str, Any]],
    answer_getter: Any,
) -> int:
    by_example: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        by_example[_example_id(row)][_route(row)] = _answer_category(answer_getter(row))
    return sum(
        len(set(route_values.values())) > 1 for route_values in by_example.values()
    )


def _category_counts(categories: Iterable[str]) -> dict[str, int]:
    counts = {category: 0 for category in ("Y", "N", "U", "F")}
    for category in categories:
        counts[category] += 1
    return counts


def _engine_product_answer(row: Mapping[str, Any]) -> str:
    trace = _answerability_trace(row)
    return str(trace.get("product_answer") or trace.get("pre_contract_answer") or "")


def _contract_post_answer(row: Mapping[str, Any]) -> str:
    trace = _answerability_trace(row)
    return str(trace.get("post_contract_answer") or "")


def _final_answer(row: Mapping[str, Any]) -> str:
    terminal = row.get("terminal_answer_state")
    if isinstance(terminal, Mapping) and terminal.get("answer") is not None:
        return str(terminal.get("answer") or "")
    return str(row.get("answer_for_scoring") or row.get("predicted_answer") or "")


def _false_abstention_entering_with_polarity(row: Mapping[str, Any]) -> bool:
    return bool(
        _gold_is_answerable(row)
        and _answer_category(_engine_product_answer(row)) in {"Y", "N"}
        and _answer_category(_final_answer(row)) == "U"
    )


def _answerability_trace(row: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = row.get("evidence_metadata")
    if not isinstance(metadata, Mapping):
        return {}
    trace = metadata.get("answerability_contract_trace")
    return trace if isinstance(trace, Mapping) else {}


def _gold_answer(row: Mapping[str, Any]) -> str:
    answers = row.get("gold_answers")
    if isinstance(answers, list) and answers:
        return str(answers[0] or "")
    return ""


def _gold_category(row: Mapping[str, Any]) -> str:
    return _answer_category(_gold_answer(row))


def _gold_is_answerable(row: Mapping[str, Any]) -> bool:
    return _gold_category(row) != "U"


def _route(row: Mapping[str, Any]) -> str:
    return str(row.get("route") or "")


def _example_id(row: Mapping[str, Any]) -> str:
    return str(row.get("example_id") or "")


def _answer_category(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = _normalized(raw)
    if normalized in {"yes", "true"}:
        return "Y"
    if normalized in {"no", "false"}:
        return "N"
    if is_abstention_answer(raw):
        return "U"
    return "F"


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())
