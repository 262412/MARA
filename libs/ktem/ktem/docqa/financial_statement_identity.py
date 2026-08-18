from __future__ import annotations

import re
from typing import Any


def source_identity(
    item: dict[str, Any], metadata: dict[str, Any] | None = None
) -> str:
    nested = metadata if isinstance(metadata, dict) else item.get("metadata")
    nested = nested if isinstance(nested, dict) else {}
    fallback = ""
    for key in ("source_id", "file_id", "document_id", "runtime_source_id"):
        for raw_value in (item.get(key), nested.get(key)):
            value = str(raw_value or "").strip()
            if not value:
                continue
            fallback = fallback or value
            if value.lower() not in {
                "unknown",
                "source:unknown",
                "none",
                "null",
                "n/a",
            }:
                return value
    return fallback


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
    atomic_kind = _atomic_metric_statement_kind(value)
    stale_balance_sheet_kind = (
        atomic_kind == "balance_sheet" and explicit_kind == "cash_flow_statement"
    )
    kind = (
        atomic_kind
        if stale_balance_sheet_kind
        else explicit_kind or atomic_kind or _statement_kind(normalized)
    )
    scope = explicit_scope or _financial_scope(normalized, kind)
    return kind, scope


def required_financial_identity(metric: str) -> tuple[str, str]:
    normalized = str(metric or "").strip().lower()
    if normalized == "inventory":
        return "balance_sheet", "consolidated"
    if normalized in {"accounts receivable", "accounts payable"}:
        return "balance_sheet", "consolidated"
    if normalized in {
        "adjusted ebitda",
    }:
        return "non_gaap_performance", ""
    if normalized in {
        "cost of goods sold",
        "gross profit",
        "net sales",
        "operating income",
        "revenue",
    }:
        return "income_statement", "consolidated"
    if normalized in {
        "net property plant and equipment",
        "total current assets",
        "current assets",
        "total current liabilities",
        "current liabilities",
    }:
        return "balance_sheet", "consolidated"
    if normalized in {"capital expenditure", "operating cash flow"}:
        return "cash_flow_statement", "consolidated"
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
            "adjusted ebitda reconciliation",
            "reconciliation of adjusted ebitda",
            "reconciliation of non gaap",
            "non gaap financial measure",
            "non gaap measures",
            "adjusted non gaap results",
        )
    ):
        return "non_gaap_performance"
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
            "statement of cash flow",
            "statements of cash flow",
            "cash flow statement",
            "cash flows from investing activities",
            "cash flows from operating activities",
            "net cash provided by operating activities",
            "net cash used in investing activities",
            "purchases of property plant and equipment",
            "purchase of property plant and equipment",
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
    ) or re.search(r"\bst\s+atements?\s+of\s+income\b", text):
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


def _atomic_metric_statement_kind(value: str | dict[str, Any]) -> str:
    if not isinstance(value, dict):
        return ""
    evidence_level = str(value.get("evidence_level") or "").strip().lower()
    row_label = _normalize(str(value.get("row_label") or ""))
    if evidence_level in {"cell", "span"} and row_label == "adjusted ebitda":
        return "non_gaap_performance"
    if evidence_level in {"cell", "span"} and row_label in {
        "capital spending",
        "capital expenditure",
        "capital expenditures",
        "purchases of property plant and equipment",
    }:
        return "cash_flow_statement"
    if evidence_level in {"cell", "span"} and row_label in {
        "current assets",
        "total current assets",
        "current liabilities",
        "total current liabilities",
        "net property plant and equipment",
        "property plant and equipment net",
    }:
        return "balance_sheet"
    return ""


def _financial_scope(text: str, statement_kind: str) -> str:
    if (
        statement_kind
        in {
            "balance_sheet",
            "income_statement",
            "cash_flow_statement",
        }
        and "consolidated" in text
    ):
        return "consolidated"
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
