from __future__ import annotations

import re

from .finance_numeric_values import question_years


def has_numeric_intent(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:amount|average|calculate|calculation|change|difference|"
            r"margin|percent(?:age)?|ratio|rate|total|turnover|value)\b",
            question,
        )
        or "free cash flow" in question
    )


def has_supported_formula_intent(question: str) -> bool:
    return any(
        term in question
        for term in (
            "capital expenditure",
            "cash conversion cycle",
            "ccc",
            "capital spending",
            "current ratio",
            "debt to equity",
            "difference",
            "free cash flow",
            "gross margin",
            "inventory turnover",
            "fixed asset turnover",
            "net fixed asset turnover",
            "ppe turnover",
            "pp&e turnover",
            "property plant and equipment turnover",
            "operating margin",
            "percent change",
            "percentage change",
            "quick ratio",
            "working capital",
        )
    ) or ("average" in question and len(question_years(question)) >= 2)
