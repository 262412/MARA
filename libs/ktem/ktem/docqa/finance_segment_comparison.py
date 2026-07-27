from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .financial_statement_identity import financial_statement_identity
from .financial_table import parse_financial_table_cells

FINANCE_SEGMENT_COMPARISON_CONTRACT = "finance_segment_comparison.v1"


@dataclass(frozen=True)
class FinanceSegmentComparisonAnswer:
    answer: str
    status: str
    periods: tuple[str, str]
    excluded_entities: tuple[str, ...]
    entity_period_values: dict[str, dict[str, str]]
    proportional_changes: dict[str, str]
    citation_ids: tuple[str, ...]
    contract_id: str = FINANCE_SEGMENT_COMPARISON_CONTRACT

    def as_trace(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["periods"] = list(self.periods)
        payload["excluded_entities"] = list(self.excluded_entities)
        payload["citation_ids"] = list(self.citation_ids)
        return payload


def finance_segment_comparison_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> FinanceSegmentComparisonAnswer | None:
    if not _is_segment_comparison(question):
        return None
    periods = _question_periods(question)
    excluded = _excluded_entities(question)
    if len(periods) != 2:
        return _result("", "missing_periods", periods, excluded, {}, {}, ())

    values, citations = _collect_segment_values(evidence_items, periods, excluded)

    complete = {
        entity: period_values
        for entity, period_values in values.items()
        if all(period in period_values for period in periods)
    }
    if len(complete) < 2:
        return _result(
            "",
            "insufficient_entities",
            periods,
            excluded,
            complete,
            {},
            _ordered_citations(complete, citations),
        )

    prior_period, current_period = periods
    changes = {
        entity: (
            (period_values[current_period] - period_values[prior_period])
            / abs(period_values[prior_period])
        )
        for entity, period_values in complete.items()
        if period_values[prior_period] != 0
    }
    if len(changes) < 2:
        return _result(
            "",
            "invalid_denominator",
            periods,
            excluded,
            complete,
            changes,
            _ordered_citations(complete, citations),
        )
    answer = max(changes, key=changes.__getitem__)
    return _result(
        answer,
        "ok",
        periods,
        excluded,
        complete,
        changes,
        _ordered_citations(complete, citations),
    )


def _collect_segment_values(
    evidence_items: list[dict[str, Any]],
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
) -> tuple[dict[str, dict[str, Decimal]], dict[str, set[str]]]:
    values: dict[str, dict[str, Decimal]] = {}
    citations: dict[str, set[str]] = {}
    for item in evidence_items:
        statement_kind, _scope = financial_statement_identity(item)
        if statement_kind and statement_kind != "segment_table":
            continue
        evidence_id = _item_id(item)
        for cell in parse_financial_table_cells(item):
            if cell.period not in periods or _is_total_row(cell.row_label):
                continue
            entity = _entity_label(cell.row_label)
            if not entity or not _valid_segment_entity(entity):
                continue
            _record_segment_value(
                values,
                citations,
                entity,
                {cell.period: cell.value},
                evidence_id,
                excluded,
            )
        for entity, period_values in _vertical_segment_values(item).items():
            _record_segment_value(
                values,
                citations,
                entity,
                period_values,
                evidence_id,
                excluded,
            )
    return values, citations


def _record_segment_value(
    values: dict[str, dict[str, Decimal]],
    citations: dict[str, set[str]],
    entity: str,
    period_values: dict[str, Decimal],
    evidence_id: str,
    excluded: tuple[str, ...],
) -> None:
    if not _valid_segment_entity(entity) or _excluded(entity, excluded):
        return
    values.setdefault(entity, {}).update(period_values)
    if evidence_id:
        citations.setdefault(entity, set()).add(evidence_id)


def _result(
    answer: str,
    status: str,
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
    values: dict[str, dict[str, Decimal]],
    changes: dict[str, Decimal],
    citation_ids: tuple[str, ...],
) -> FinanceSegmentComparisonAnswer:
    normalized_periods = (periods[0], periods[1]) if len(periods) >= 2 else ("", "")
    return FinanceSegmentComparisonAnswer(
        answer=answer,
        status=status,
        periods=normalized_periods,
        excluded_entities=excluded,
        entity_period_values={
            entity: {period: str(value) for period, value in period_values.items()}
            for entity, period_values in values.items()
        },
        proportional_changes={
            entity: str(change) for entity, change in changes.items()
        },
        citation_ids=citation_ids,
    )


def _question_periods(question: str) -> tuple[str, ...]:
    values = []
    for full, short in re.findall(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\b|\bfy\s*(\d{2})\b",
        str(question or ""),
        flags=re.IGNORECASE,
    ):
        values.append(full or f"20{short}")
    return tuple(sorted(dict.fromkeys(values)))


def _excluded_entities(question: str) -> tuple[str, ...]:
    match = re.search(
        r"\bexcluding\s+([a-z][a-z0-9 &-]*?)(?:,|\bin\b|\bwhich\b|$)",
        str(question or "").lower(),
    )
    if not match:
        return ()
    return tuple(_title(value) for value in match.group(1).split(" and ") if value)


def _is_segment_comparison(question: str) -> bool:
    lowered = str(question or "").lower()
    return (
        "segment" in lowered
        and "proportion" in lowered
        and bool(re.search(r"\b(?:most|least|largest|smallest)\b", lowered))
    )


def _entity_label(row_label: str) -> str:
    value = re.sub(
        r"\b(?:net\s+)?(?:sales|revenue|revenues)\b",
        "",
        str(row_label or ""),
        flags=re.IGNORECASE,
    ).strip(" :-")
    return _title(value)


def _title(value: str) -> str:
    return " ".join(
        token.upper() if token.lower() in {"amd", "gpu"} else token.capitalize()
        for token in str(value or "").strip().split()
    )


def _excluded(entity: str, excluded: tuple[str, ...]) -> bool:
    lowered = entity.lower()
    return any(value.lower() in lowered for value in excluded)


def _is_total_row(row_label: str) -> bool:
    return str(row_label or "").strip().lower().startswith("total")


def _valid_segment_entity(entity: str) -> bool:
    lowered = str(entity or "").strip().lower()
    if not lowered or len(lowered) > 64:
        return False
    return not any(
        phrase in lowered
        for phrase in (
            "each of the",
            "months ended",
            "period ended",
            "year ended",
            "december",
            "september",
            "june",
            "march",
        )
    )


def _item_id(item: dict[str, Any]) -> str:
    return str(
        item.get("evidence_id")
        or item.get("element_id")
        or item.get("canonical_id")
        or ""
    ).strip()


def _vertical_segment_values(
    item: dict[str, Any],
) -> dict[str, dict[str, Decimal]]:
    text = str(item.get("text") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    periods = tuple(dict.fromkeys(re.findall(r"\b(?:19|20)\d{2}\b", text)))
    if len(periods) < 2:
        return {}
    try:
        start = next(
            index + 1
            for index, line in enumerate(lines)
            if re.fullmatch(
                r"(?:net\s+)?(?:sales|revenue|revenues)\s*:?",
                line,
                flags=re.IGNORECASE,
            )
        )
    except StopIteration:
        return {}
    end = next(
        (
            index
            for index in range(start, len(lines))
            if re.match(
                r"(?:total\s+(?:net\s+)?(?:sales|revenue)|" r"operating\s+income)",
                lines[index],
                flags=re.IGNORECASE,
            )
        ),
        len(lines),
    )
    values: dict[str, dict[str, Decimal]] = {}
    index = start
    while index < end:
        label = lines[index]
        if not re.search(r"[A-Za-z]", label):
            index += 1
            continue
        numeric_values: list[Decimal] = []
        cursor = index + 1
        while cursor < end and not re.search(r"[A-Za-z]", lines[cursor]):
            value = _decimal_line(lines[cursor])
            if value is not None:
                numeric_values.append(value)
            cursor += 1
        if len(numeric_values) >= len(periods):
            values[_title(label)] = {
                period: value
                for period, value in zip(periods, numeric_values[: len(periods)])
            }
        index = max(cursor, index + 1)
    return values


def _decimal_line(value: str) -> Decimal | None:
    text = str(value or "").strip().replace("$", "").replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    if not re.fullmatch(r"\(?[+-]?\d+(?:\.\d+)?\)?", text):
        return None
    try:
        parsed = Decimal(text.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _ordered_citations(
    values: dict[str, dict[str, Decimal]],
    citations: dict[str, set[str]],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            citation
            for entity in values
            for citation in sorted(citations.get(entity, set()))
        )
    )
