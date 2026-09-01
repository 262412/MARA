from __future__ import annotations

import re
from typing import Any

from ktem.docqa.visual_evidence_authority import record_visual_answer_authority

from .mara_messages import MARA_VISUAL_EVIDENCE_ONLY_MESSAGE


def route_visual_answer(
    pipeline: Any,
    request: Any,
    bundle: Any,
    *,
    evidence_only_fallback: bool,
) -> str | None:
    ocr_answer = _ocr_first_visual_answer(request, bundle)
    if ocr_answer:
        bundle.metadata["generation_backend"] = "ocr_first_visual_extractor"
        bundle.metadata["visual_generation_gate"] = "ocr_first_answer"
        record_visual_answer_authority(
            bundle,
            ocr_answer,
            backend="ocr_first_visual_extractor",
        )
        return ocr_answer
    vlm_generator = getattr(pipeline, "vlm_generator", None)
    if vlm_generator is None:
        if not evidence_only_fallback:
            return None
        bundle.metadata["generation_backend"] = "evidence_only_without_vlm"
        return _visual_evidence_only_answer(bundle)
    generator_name = str(getattr(vlm_generator, "name", "visual_generator"))
    bundle.metadata["generation_backend"] = generator_name
    cache_key = _visual_answer_cache_key(request, bundle, generator_name)
    cache = getattr(pipeline, "_mara_vlm_answer_cache", None)
    if cache is None:
        cache = {}
        setattr(pipeline, "_mara_vlm_answer_cache", cache)
    if cache_key in cache:
        bundle.metadata["vlm_cache"] = {"hit": True, "key": cache_key}
        answer = str(cache[cache_key])
        record_visual_answer_authority(bundle, answer, backend=generator_name)
        return answer
    answer = _visual_generator_answer(vlm_generator, request, bundle)
    if answer.strip():
        cache[cache_key] = answer
        record_visual_answer_authority(bundle, answer, backend=generator_name)
    bundle.metadata["vlm_cache"] = {"hit": False, "key": cache_key}
    return answer


def _visual_evidence_only_answer(bundle: Any) -> str:
    pages = [
        f"{item.get('source_name') or item.get('source_id')} page {item.get('page_label')}"
        for item in bundle.items
        if item.get("modality") == "page_image"
    ]
    if not pages:
        return MARA_VISUAL_EVIDENCE_ONLY_MESSAGE
    preview = "; ".join(str(page) for page in pages[:3])
    return f"{MARA_VISUAL_EVIDENCE_ONLY_MESSAGE} Evidence: {preview}."


def _visual_generator_answer(generator: Any, request: Any, bundle: Any) -> str:
    if hasattr(generator, "generate"):
        return str(generator.generate(request, bundle))
    if callable(generator):
        return str(generator(request, bundle))
    raise ValueError("Configured visual generator must be callable or expose generate.")


def _ocr_first_visual_answer(request: Any, bundle: Any) -> str:
    if not _should_use_ocr_first_visual(request):
        return ""
    question_tokens = _meaningful_question_tokens(
        str(getattr(request, "prompt", "") or "")
    )
    candidates = _visual_ocr_sentences(bundle)
    ranked = sorted(
        (
            (_overlap_count(sentence, question_tokens), index, sentence)
            for index, sentence in enumerate(candidates)
        ),
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )
    for _score, _index, sentence in ranked:
        answer = _short_span_from_ocr_sentence(sentence)
        if answer:
            return answer
    return ""


def _should_use_ocr_first_visual(request: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    origin = str(getattr(request, "origin", "") or "").strip().lower()
    return "mmdocrag" in domain or origin == "benchmark"


def _visual_ocr_sentences(bundle: Any) -> list[str]:
    sentences: list[str] = []
    for item in getattr(bundle, "items", []) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("modality") or "") not in {"page_image", "image", "figure"}:
            continue
        text = " ".join(
            str(item.get(key) or "").strip()
            for key in ("ocr_text", "selected_text", "text")
            if str(item.get(key) or "").strip()
        )
        for sentence in re.split(r"[\n.;]+", text):
            value = " ".join(sentence.split())
            if value:
                sentences.append(value)
    return sentences


def _short_span_from_ocr_sentence(sentence: str) -> str:
    patterns = (
        r"\b(?:answer|label|title|value|amount|name)\s+(?:is|was|are|were)\s+(.+)$",
        r"\b(?:is|was|are|were)\s+shown\s+as\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = _clean_ocr_answer_candidate(match.group(1))
        if _looks_like_short_visual_answer(candidate):
            return candidate
    return ""


def _clean_ocr_answer_candidate(candidate: str) -> str:
    value = str(candidate or "").strip().strip("\"'` ")
    value = re.split(r"\s+(?:according to|because|from the|on the page)\b", value, 1)[0]
    return value.strip(" .,:;")


def _looks_like_short_visual_answer(candidate: str) -> bool:
    words = str(candidate or "").split()
    return bool(candidate.strip()) and len(words) <= 8


def _meaningful_question_tokens(question: str) -> set[str]:
    stopwords = {
        "what",
        "which",
        "where",
        "when",
        "does",
        "did",
        "the",
        "this",
        "that",
        "shown",
        "show",
        "page",
        "slide",
        "figure",
        "image",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", question.lower())
        if len(token) > 2 and token not in stopwords
    }


def _overlap_count(sentence: str, tokens: set[str]) -> int:
    if not tokens:
        return 0
    sentence_tokens = set(re.findall(r"[a-zA-Z0-9]+", sentence.lower()))
    return len(sentence_tokens & tokens)


def _visual_answer_cache_key(request: Any, bundle: Any, generator_name: str) -> str:
    item = _first_page_image_item(bundle)
    return "|".join(
        (
            generator_name,
            str(getattr(request, "prompt", "") or ""),
            str(getattr(request, "origin", "") or ""),
            str(item.get("source_id") or item.get("file_id") or ""),
            str(item.get("page_label") or item.get("page_number") or ""),
            str(item.get("evidence_id") or ""),
        )
    )


def _first_page_image_item(bundle: Any) -> dict[str, Any]:
    for item in getattr(bundle, "items", []) or []:
        if isinstance(item, dict) and str(item.get("modality") or "") == "page_image":
            return item
    return {}
