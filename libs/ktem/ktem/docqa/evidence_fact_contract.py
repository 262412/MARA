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


class EvidenceIdentityConflictError(ValueError):
    """Raised when one immutable evidence atom has conflicting facts."""
