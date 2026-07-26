from __future__ import annotations

import re
from typing import Any


def financial_statement_identity(
    value: str | dict[str, Any],
) -> tuple[str, str]:
    """Infer the financial statement family and accounting scope.

    The inference deliberately uses explicit headings and scope phrases. It is
    not a topical classifier: an occurrence of "inventory" alone must not turn
    an arbitrary table into a consolidated balance-sheet fact.
    """
    if isinstance(value, dict):
        metadata = value.get("metadata")
        nested = metadata if isinstance(metadata, dict) else {}
        explicit_kind = str(
            value.get("statement_kind") or nested.get("statement_kind") or ""
        ).strip()
        explicit_scope = str(
            value.get("financial_scope") or nested.get("financial_scope") or ""
        ).strip()
        text = _item_text(value)
    else:
        explicit_kind = ""
        explicit_scope = ""
        text = str(value or "")
    normalized = _normalize(text)
    kind = explicit_kind or _statement_kind(normalized)
    scope = explicit_scope or _financial_scope(normalized, kind)
    return kind, scope


def required_financial_identity(metric: str) -> tuple[str, str]:
    normalized = str(metric or "").strip().lower()
    if normalized == "inventory":
        return "balance_sheet", "consolidated"
    if normalized == "cost of goods sold":
        return "income_statement", "consolidated"
    return "", ""


def required_operand_identity(operand_id: str) -> tuple[str, str]:
    canonical = re.sub(
        r"_(?:19|20)\d{2}$",
        "",
        str(operand_id or ""),
    ).replace("_", " ")
    if canonical == "inventories":
        canonical = "inventory"
    return required_financial_identity(canonical)


def compatible_financial_identity(
    value: str | dict[str, Any],
    required_statement_kind: str,
    required_scope: str,
) -> bool:
    statement_kind, financial_scope = financial_statement_identity(value)
    if (
        required_statement_kind
        and statement_kind
        and required_statement_kind != statement_kind
    ):
        return False
    if required_scope and financial_scope and required_scope != financial_scope:
        return False
    return True


def matches_required_financial_identity(
    value: str | dict[str, Any],
    required_statement_kind: str,
    required_scope: str,
) -> bool:
    statement_kind, financial_scope = financial_statement_identity(value)
    if required_statement_kind and statement_kind != required_statement_kind:
        return False
    if required_scope and financial_scope != required_scope:
        return False
    return True


def _statement_kind(text: str) -> str:
    if any(
        phrase in text
        for phrase in (
            "reporting segment",
            "reportable segment",
            "revenue by segment",
            "net revenue by segment",
            "segment net revenue",
        )
    ):
        return "segment_table"
    if any(
        phrase in text
        for phrase in (
            "statement of cash flows",
            "statements of cash flows",
            "cash flow statement",
        )
    ):
        return "cash_flow_statement"
    if any(
        phrase in text
        for phrase in (
            "balance sheet",
            "balances sheets",
            "statement of financial position",
            "statements of financial position",
        )
    ):
        return "balance_sheet"
    if any(
        phrase in text
        for phrase in (
            "statement of income",
            "statements of income",
            "statement of operations",
            "statements of operations",
            "income statement",
        )
    ):
        return "income_statement"
    if any(
        phrase in text
        for phrase in (
            "pension",
            "postretirement",
            "performance stock unit",
            "share based compensation",
        )
    ):
        return "compensation_or_benefit_table"
    return ""


def _financial_scope(text: str, statement_kind: str) -> str:
    if "held for sale" in text or "assets held for sale" in text:
        return "held_for_sale"
    if any(
        phrase in text
        for phrase in (
            "purchase price allocation",
            "business acquisition",
            "acquisition date fair value",
        )
    ):
        return "acquisition"
    if statement_kind == "segment_table":
        return "segment"
    if "consolidated" in text:
        return "consolidated"
    return ""


def _item_text(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return " ".join(
        str(value or "")
        for value in (
            item.get("text"),
            item.get("ocr_text"),
            item.get("vlm_text"),
            item.get("caption"),
            nested.get("table_title"),
            nested.get("section_title"),
        )
    )


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))
