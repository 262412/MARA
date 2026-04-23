import re
from dataclasses import dataclass
from typing import Literal


QueryModality = Literal["text", "table", "figure", "formula", "mixed"]


@dataclass(frozen=True)
class QueryRoute:
    query: str
    modality: QueryModality
    modality_weights: dict[str, float]
    retrieval_hints: dict[str, list[str]]


class QueryRouter:
    """Route lightweight retrieval queries by modality-oriented signals."""

    _SIGNALS: dict[str, tuple[str, ...]] = {
        "formula": (
            "\u516c\u5f0f",
            "\u65b9\u7a0b",
            "\u53d8\u91cf",
            "\u7b26\u53f7",
            "\u5b9a\u7406",
            "equation",
            "eq.",
            "formula",
            "=",
            "\u2211",
            "\u222b",
            "\u03b1",
            "\u03b2",
            "\u03b3",
            "\u03b4",
            "\u03b8",
            "\u03bc",
            "\u03c0",
            "\u03c3",
            "\u03c9",
            "\u03c6",
        ),
        "figure": (
            "\u56fe",
            "\u56fe\u7247",
            "\u56fe\u8868",
            "figure",
            "chart",
            "image",
            "diagram",
            "flowchart",
        ),
        "table": (
            "\u8868",
            "\u8868\u683c",
            "table",
            "cell",
            "row",
            "column",
            "\u6392\u540d",
            "\u6392\u5e8f",
            "\u6700\u5927",
            "\u6700\u5c0f",
            "\u5408\u8ba1",
            "\u5e73\u5747",
        ),
    }
    _MODALITIES = ("text", "table", "figure", "formula")

    def route(self, query: str) -> QueryRoute:
        matched = self._matched_modalities(query)
        modality: QueryModality
        if not matched:
            modality = "text"
        elif len(matched) == 1:
            modality = matched[0]  # type: ignore[assignment]
        else:
            modality = "mixed"

        return QueryRoute(
            query=query,
            modality=modality,
            modality_weights=self._weights(matched),
            retrieval_hints={"boost_element_types": matched or ["text"]},
        )

    def _matched_modalities(self, query: str) -> list[str]:
        normalized = query.lower()
        return [
            modality
            for modality in ("formula", "figure", "table")
            if any(
                self._contains_signal(normalized, signal)
                for signal in self._SIGNALS[modality]
            )
        ]

    def _contains_signal(self, query: str, signal: str) -> bool:
        normalized_signal = signal.lower()
        if normalized_signal.endswith("."):
            return (
                re.search(rf"(?<!\w){re.escape(normalized_signal)}(?!\w)", query)
                is not None
            )
        if normalized_signal.isascii() and normalized_signal.replace(".", "").isalpha():
            return re.search(rf"\b{re.escape(normalized_signal)}\b", query) is not None
        return normalized_signal in query

    def _weights(self, matched: list[str]) -> dict[str, float]:
        if not matched:
            return {
                modality: (1.0 if modality == "text" else 0.0)
                for modality in self._MODALITIES
            }
        return {
            modality: (
                1.0 if modality in matched else 0.2 if modality == "text" else 0.0
            )
            for modality in self._MODALITIES
        }


def route_query(query: str) -> QueryRoute:
    return QueryRouter().route(query)
