from __future__ import annotations

from typing import Any

MAX_IMAGES = 10
CITATION_TIMEOUT = 5.0

_PAGE_VISUAL_CONTEXT_KEYS = (
    "thumbnail_doc_id",
    "page_thumbnail_doc_id",
    "page_image_origin",
    "page_image",
    "preview_image",
    "rendered_page_image",
)
_VISUAL_CONTEXT_TERMS = (
    "figure",
    "fig.",
    "image",
    "diagram",
    "chart",
    "graph",
    "flowchart",
    "plot",
    "box",
    "arrow",
    "node",
    "edge",
    "layout",
    "visual",
    "\u56fe",
    "\u56fe\u7247",
    "\u56fe\u50cf",
    "\u56fe\u793a",
    "\u793a\u610f\u56fe",
    "\u6d41\u7a0b\u56fe",
    "\u7ed3\u6784\u56fe",
    "\u6846",
    "\u7ebf\u6846",
    "\u7bad\u5934",
    "\u8282\u70b9",
    "\u5e03\u5c40",
)


def looks_like_visual_question_or_answer(*texts: str) -> bool:
    combined = " ".join(str(text or "").casefold() for text in texts)
    return any(term in combined for term in _VISUAL_CONTEXT_TERMS)


def llm_generation_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        key: kwargs[key]
        for key in ("temperature", "top_p", "seed")
        if key in kwargs and kwargs[key] is not None
    }


DEFAULT_QA_TEXT_PROMPT = (
    "Use the following pieces of context to answer the question at the end in detail with clear explanation. "  # noqa: E501
    "If you don't know the answer, just say that you don't know, don't try to "
    "make up an answer. "
    "Return the final answer as Markdown, not raw HTML. Do not return one unbroken paragraph; put a blank line between paragraphs, headings, lists, formulas, and tables. "
    "If the user asks for a table, comparison, matrix, or summary table, you MUST include a Markdown table with a header and separator row, e.g. | Aspect | Summary | and | --- | --- |. Put a blank line before and after the table; never write pipe-delimited table rows inline inside a paragraph. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. Do not use backticks for mathematical variables or equations. For code, use fenced Markdown code blocks with triple backticks such as ```python when a language tag is clear. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "{context}\n"
    "Question: {question}\n"
    "Helpful Answer:"
)

DEFAULT_QA_TABLE_PROMPT = (
    "Use the given context: texts, tables, and figures below to answer the question, "
    "then provide answer with clear explanation. "
    "If you don't know the answer, just say that you don't know, "
    "don't try to make up an answer. "
    "Return the final answer as Markdown, not raw HTML. Do not return one unbroken paragraph; put a blank line between paragraphs, headings, lists, formulas, and tables. "
    "If the user asks for a table, comparison, matrix, or summary table, you MUST include a Markdown table with a header and separator row, e.g. | Aspect | Summary | and | --- | --- |. Put a blank line before and after the table; never write pipe-delimited table rows inline inside a paragraph. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. Do not use backticks for mathematical variables or equations. For code, use fenced Markdown code blocks with triple backticks such as ```python when a language tag is clear. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "Context:\n"
    "{context}\n"
    "Question: {question}\n"
    "Helpful Answer:"
)  # noqa

DEFAULT_QA_CHATBOT_PROMPT = (
    "Pick the most suitable chatbot scenarios to answer the question at the end, "
    "output the provided answer text. If you don't know the answer, "
    "just say that you don't know. Keep the answer as concise as possible. "
    "Give answer in {lang}.\n\n"
    "Context:\n"
    "{context}\n"
    "Question: {question}\n"
    "Answer:"
)  # noqa

DEFAULT_QA_FIGURE_PROMPT = (
    "Use the given context: texts, tables, and figures below to answer the question. "
    "If you don't know the answer, just say that you don't know. "
    "Return the final answer as Markdown, not raw HTML. Do not return one unbroken paragraph; put a blank line between paragraphs, headings, lists, formulas, and tables. "
    "If the user asks for a table, comparison, matrix, or summary table, you MUST include a Markdown table with a header and separator row, e.g. | Aspect | Summary | and | --- | --- |. Put a blank line before and after the table; never write pipe-delimited table rows inline inside a paragraph. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. Do not use backticks for mathematical variables or equations. For code, use fenced Markdown code blocks with triple backticks such as ```python when a language tag is clear. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "Context: \n"
    "{context}\n"
    "Question: {question}\n"
    "Answer: "
)  # noqa
