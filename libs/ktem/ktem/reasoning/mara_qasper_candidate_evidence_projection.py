from __future__ import annotations

from typing import Any

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")


def exact_selector_valid(
    selector: dict[str, Any],
    *,
    record_text: Any,
    record_text_start: Any,
) -> bool:
    selector_id = str(selector.get("selector_id") or "").strip()
    text = str(selector.get("text") or "")
    canonical_text = str(record_text) if isinstance(record_text, str) else ""
    start = selector.get("span_start")
    end = selector.get("span_end")
    text_start = (
        record_text_start
        if isinstance(record_text_start, int)
        and not isinstance(record_text_start, bool)
        and record_text_start >= 0
        else 0
    )
    local_start = start - text_start if isinstance(start, int) else -1
    local_end = end - text_start if isinstance(end, int) else -1
    return bool(
        selector_id
        and text
        and isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and start >= 0
        and end > start
        and end - start == len(text)
        and local_start >= 0
        and local_end <= len(canonical_text)
        and canonical_text[local_start:local_end] == text
    )


def span_set_refs(selectors: tuple[dict[str, Any], ...] | None) -> list[str]:
    return [str(selector["selector_id"]) for selector in selectors or ()]


def span_set_spans(
    selectors: tuple[dict[str, Any], ...] | None,
) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": str(selector["evidence_id"]),
            "evidence_ref": str(selector["selector_id"]),
            "text": str(selector["text"]),
            "span_start": selector["span_start"],
            "span_end": selector["span_end"],
        }
        for selector in selectors or ()
    ]


def span_set_slot_refs(
    selectors: tuple[dict[str, Any], ...] | None,
) -> dict[str, list[str]]:
    return {
        slot: [
            str(selector["selector_id"])
            for selector in selectors or ()
            if slot in selector["slot_hints"]
        ]
        for slot in _PROPOSITION_SLOTS
        if any(slot in selector["slot_hints"] for selector in selectors or ())
    }
