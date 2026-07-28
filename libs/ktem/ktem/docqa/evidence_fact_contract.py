STRUCTURED_FACT_FIELDS = (
    "cell_id",
    "table_id",
    "row_index",
    "column_index",
    "row_label",
    "column_label",
    "period",
    "period_kind",
    "value",
    "unit",
    "scale",
    "currency",
    "statement_kind",
    "financial_scope",
)
_POSITIVE = {"increase", "increased", "rise", "rose", "growth", "higher", "up"}
_NEGATIVE = {"decrease", "decreased", "decline", "declined", "lower", "down"}


class EvidenceIdentityConflictError(ValueError):
    """Raised when one immutable evidence atom has conflicting facts."""


def fact_sets_conflict(
    left_kind: str,
    right_kind: str,
    left_values: set[str],
    right_values: set[str],
) -> bool:
    if not left_values or not right_values or left_values == right_values:
        return False
    if left_kind in {"cell", "span"} or right_kind in {"cell", "span"}:
        return True
    return not (left_values <= right_values or right_values <= left_values)


def polarity(tokens: set[str]) -> str:
    if tokens & _POSITIVE:
        return "positive"
    if tokens & _NEGATIVE:
        return "negative"
    return ""
