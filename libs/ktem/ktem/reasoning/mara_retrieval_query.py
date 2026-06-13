from __future__ import annotations

ANSWER_FORMAT_MARKER = "\n\nAnswer formatting requirements:"


def messages_share_retrieval_cache_key(cached_message: str, message: str) -> bool:
    if message == cached_message:
        return True
    return str(message or "").startswith(
        str(cached_message or "").rstrip() + ANSWER_FORMAT_MARKER
    )


def retrieval_query(message: str) -> str:
    question = str(message or "").split(ANSWER_FORMAT_MARKER, 1)[0]
    focus_terms = _finance_retrieval_focus_terms(question)
    if not focus_terms:
        return question
    return f"{question}\n\nRetrieval focus: {'; '.join(focus_terms)}."


def _finance_retrieval_focus_terms(question: str) -> list[str]:
    normalized = str(question or "").lower()
    if "quick ratio" in normalized:
        return [
            "Consolidated Balance Sheet",
            "Total current assets",
            "Total current liabilities",
            "Inventories",
            "Cash and cash equivalents",
            "Marketable securities",
            "Accounts receivable",
        ]
    if "working capital" in normalized:
        return [
            "Consolidated Balance Sheet",
            "Total current assets",
            "Total current liabilities",
            "Current assets",
            "Current liabilities",
        ]
    if "inventory turnover" in normalized:
        return [
            "Consolidated Statement of Income",
            "Consolidated Balance Sheet",
            "Cost of sales",
            "Cost of goods sold",
            "Inventories",
        ]
    return []
