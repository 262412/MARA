from __future__ import annotations

from typing import Any


def retrieval_adequacy_issue(
    prompt: str,
    evidence_metadata: dict[str, Any],
    *,
    domain: str | None = None,
    require_page_scoped: bool = True,
) -> str:
    if not _finance_domain_enabled(domain):
        return ""
    requirements = _financial_statement_requirements(prompt)
    if not requirements:
        return ""
    evidence_text = _combined_evidence_text(evidence_metadata).lower()
    missing = [
        label
        for label, aliases in requirements
        if not any(alias in evidence_text for alias in aliases)
    ]
    if require_page_scoped and not _has_page_scoped_evidence(evidence_metadata):
        return "Retrieved evidence lacks page-scoped financial statement support."
    present_count = len(requirements) - len(missing)
    if missing and present_count <= 0:
        return (
            "Retrieved evidence lacks financial statement fields needed for "
            f"generation: {', '.join(missing)}."
        )
    return ""


def financial_statement_match_count(
    prompt: str,
    evidence_text: str,
    *,
    domain: str | None = None,
) -> int:
    if not _finance_domain_enabled(domain):
        return 0
    requirements = _financial_statement_requirements(prompt)
    if not requirements:
        return 0
    lowered = str(evidence_text or "").lower()
    return sum(1 for _label, aliases in requirements if _has_any(lowered, aliases))


def _finance_domain_enabled(domain: str | None) -> bool:
    return str(domain or "").strip().lower() in {"finance", "financial"}


def _financial_statement_requirements(
    prompt: str,
) -> list[tuple[str, tuple[str, ...]]]:
    lowered = str(prompt or "").lower()
    for requirement_builder in (
        _liquidity_requirements,
        _turnover_and_receivable_requirements,
        _capital_asset_requirements,
        _operating_segment_requirements,
        _customer_geography_requirements,
        _security_dividend_requirements,
    ):
        requirements = requirement_builder(lowered)
        if requirements:
            return requirements
    return []


def _liquidity_requirements(value: str) -> list[tuple[str, tuple[str, ...]]]:
    if "quick ratio" in value:
        return [
            ("current assets", ("current assets", "total current assets")),
            (
                "current liabilities",
                ("current liabilities", "total current liabilities"),
            ),
            ("inventories", ("inventories", "inventory", "total inventories")),
        ]
    if "working capital" in value:
        return [
            ("current assets", ("current assets", "total current assets")),
            (
                "current liabilities",
                ("current liabilities", "total current liabilities"),
            ),
        ]
    return []


def _turnover_and_receivable_requirements(
    value: str,
) -> list[tuple[str, tuple[str, ...]]]:
    if "inventory turnover" in value:
        return [
            ("cost of sales", ("cost of sales", "cost of goods sold", "cogs")),
            ("inventories", ("inventories", "inventory")),
        ]
    if _has_any(value, ("days payable outstanding", "dpo")):
        return [
            ("accounts payable", ("accounts payable",)),
            ("cost of sales", ("cost of sales", "cost of goods sold", "cogs")),
            ("inventories", ("inventories", "inventory")),
        ]
    if _has_any(value, ("net ar", "accounts receivable", "trade receivables")):
        return [
            (
                "balance sheet",
                (
                    "balance sheet",
                    "balance sheets",
                    "statement of financial position",
                ),
            ),
            (
                "receivables",
                (
                    "trade receivables",
                    "trade receivables, net",
                    "accounts receivable",
                    "receivables, net",
                ),
            ),
        ]
    return []


def _capital_asset_requirements(value: str) -> list[tuple[str, tuple[str, ...]]]:
    if _has_any(value, ("capital expenditure", "capex")):
        return [
            (
                "cash flow statement",
                (
                    "statement of cash flows",
                    "statement of cash flow",
                    "cash flows from operating activities",
                ),
            ),
            (
                "capital expenditures",
                (
                    "capital expenditures",
                    "capital expenditure",
                    "purchases of property, plant and equipment",
                    "purchase of property, plant and equipment",
                ),
            ),
        ]
    if _has_any(value, ("capital-intensive", "capital intensive")):
        return [
            ("net sales", ("net sales", "net revenue", "net revenues")),
            (
                "property, plant and equipment",
                (
                    "property, plant and equipment",
                    "property and equipment",
                    "plant and equipment",
                ),
            ),
            (
                "capital expenditures",
                (
                    "capital expenditures",
                    "capital expenditure",
                    "purchases of property, plant and equipment",
                    "purchase of property, plant and equipment",
                ),
            ),
            ("total assets", ("total assets",)),
        ]
    if _has_any(value, ("net ppne", "ppne", "pp&e", "fixed asset turnover")):
        return [
            (
                "property and equipment",
                (
                    "property, plant and equipment",
                    "property and equipment",
                    "plant and equipment",
                ),
            ),
        ]
    return []


def _operating_segment_requirements(value: str) -> list[tuple[str, tuple[str, ...]]]:
    if "operating margin" in value:
        return [
            ("net sales", ("net sales", "net revenue", "net revenues")),
            ("operating income", ("operating income", "operating profit")),
        ]
    if "segment" in value and _has_any(
        value,
        ("m&a", "acquisition", "divestiture", "organic", "growth"),
    ):
        return [
            ("business segment", ("business segment", "by business segment")),
            ("organic sales", ("organic sales", "organic growth")),
        ]
    return []


def _customer_geography_requirements(
    value: str,
) -> list[tuple[str, tuple[str, ...]]]:
    if _has_any(value, ("primary customers", "customer base")):
        return [
            ("commercial airlines", ("commercial airlines", "commercial airline")),
            (
                "U.S. government",
                (
                    "u.s. government",
                    "us government",
                    "united states government",
                    "government contracts",
                ),
            ),
        ]
    if _has_any(value, ("geographies", "geography", "geographic regions")):
        return [
            ("geographic regions", ("geographic regions", "geography")),
            ("United States", ("united states",)),
            ("EMEA", ("emea",)),
            ("APAC", ("apac",)),
            ("LACC", ("lacc",)),
        ]
    return []


def _security_dividend_requirements(value: str) -> list[tuple[str, tuple[str, ...]]]:
    if _has_any(value, ("debt securities", "trading symbol")):
        return [
            ("registered securities", ("title of each class", "trading symbol")),
            ("exchange", ("name of each exchange", "new york stock exchange")),
        ]
    if "dividend" in value:
        return [
            ("dividend", ("dividend", "dividends")),
        ]
    return []


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _combined_evidence_text(evidence_metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in evidence_metadata.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        metadata = _item_metadata(item)
        for key in ("text", "caption", "ocr_text", "vlm_text", "source_name"):
            parts.append(str(item.get(key) or ""))
        for key in ("page_label", "section", "table_origin"):
            parts.append(str(metadata.get(key) or ""))
    return " ".join(parts)


def _has_page_scoped_evidence(evidence_metadata: dict[str, Any]) -> bool:
    if evidence_metadata.get("page_coverage"):
        return True
    for item in evidence_metadata.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("page_label") or "").strip():
            return True
        metadata = _item_metadata(item)
        if str(metadata.get("page_label") or "").strip():
            return True
        backrefs = item.get("source_backrefs") or metadata.get("source_backrefs") or []
        if any("#page:" in str(ref) for ref in backrefs):
            return True
    return False


def _item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata
