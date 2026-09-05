from __future__ import annotations

import importlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from ktem.docqa.evidence_text import extract_final_answer_text

from .metrics import (
    formula_normalized_match_score,
    normalize_text,
    numeric_tolerance_score,
    round_metric,
)

SEMANTIC_ANSWER_CONTRACT = "semantic_answer_core_extensions_v1"
SEMANTIC_JUDGE_PROMPT_CONTRACT = "semantic_core_extensions_judge_prompt_v1"
DEFAULT_SEMANTIC_JUDGE_MODEL = "Qwen/Qwen3-8B"
DEFAULT_SEMANTIC_JUDGE_BASE_URL = "http://localhost:8000/v1"

SemanticJudge = Callable[[dict[str, Any]], dict[str, Any]]

_BOOLEAN_ALIASES = {
    "yes": True,
    "true": True,
    "1": True,
    "no": False,
    "false": False,
    "0": False,
}
_UNANSWERABLE = {
    "unanswerable",
    "not answerable",
    "insufficient evidence",
    "not enough evidence",
}
_DATE_RE = re.compile(
    r"\b(?:19|20)\d{2}(?:[-/]\d{1,2}(?:[-/]\d{1,2})?)?\b|"
    r"\b(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_DATE_ONLY_RE = re.compile(
    r"^(?:(?:19|20)\d{2}(?:[-/]\d{1,2}(?:[-/]\d{1,2})?)?|"
    r"(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+(?:19|20)\d{2})$",
    re.IGNORECASE,
)
_LIST_TYPES = {"list", "list_qa", "multi_answer", "multiple_answers"}
_FORMULA_TYPES = {"formula", "math", "math_formula", "equation"}
_NUMERIC_TYPES = {
    "numeric",
    "number",
    "calculation",
    "currency",
    "percentage",
    "ratio",
}


@dataclass(frozen=True)
class LocalSemanticJudge:
    model: str = DEFAULT_SEMANTIC_JUDGE_MODEL
    base_url: str = DEFAULT_SEMANTIC_JUDGE_BASE_URL
    timeout_seconds: float = 60.0
    api_key: str = ""

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers=_judge_headers(self.api_key),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
        return _parse_judge_json(content)


def local_semantic_judge(
    *,
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
) -> LocalSemanticJudge:
    return LocalSemanticJudge(
        model=str(model or DEFAULT_SEMANTIC_JUDGE_MODEL),
        base_url=str(
            base_url
            or os.getenv("MARA_LLM_BASE_URL")
            or DEFAULT_SEMANTIC_JUDGE_BASE_URL
        ),
        timeout_seconds=float(timeout_seconds),
        api_key=str(os.getenv("MARA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""),
    )


def semantic_judge_backend(
    backend: str | None,
    *,
    model: str | None = None,
    timeout_seconds: float = 60.0,
) -> SemanticJudge | None:
    value = str(backend or "off").strip()
    if value.lower() in {"", "off", "none"}:
        return None
    if value.lower() in {
        "on",
        "true",
        "1",
        "local",
        "local_qwen3_8b",
        "builtin:local_qwen3_8b",
    }:
        return local_semantic_judge(
            model=model,
            timeout_seconds=timeout_seconds,
        )
    module_name, separator, attribute = value.rpartition(".")
    if not separator:
        raise ValueError(
            "semantic evaluator must be off, on, local_qwen3_8b, or a Python path"
        )
    candidate = getattr(importlib.import_module(module_name), attribute)
    if not callable(candidate):
        raise TypeError(f"Semantic evaluator backend is not callable: {value}")
    return candidate


def semantic_answer_metrics(
    prediction: dict[str, Any],
    *,
    judge: SemanticJudge | None = None,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    answer_type = _answer_type(prediction)
    metadata: dict[str, Any] = {
        "contract_id": SEMANTIC_ANSWER_CONTRACT,
        "answer_type": answer_type,
        "method": "",
        "judge_status": "not_required",
        "prompt_contract": SEMANTIC_JUDGE_PROMPT_CONTRACT,
        "judge_model": str(getattr(judge, "model", "") or ""),
    }
    if answer_type == "verification":
        metadata.update(method="dataset_native", judge_status="not_applicable")
        return _empty_metrics(), metadata

    if prediction.get("error"):
        metadata.update(
            method="invalid_prediction",
            judge_status="error",
            error=str(prediction.get("error") or "prediction execution failed"),
        )
        return _empty_metrics(), metadata

    deterministic = _deterministic_score(prediction, answer_type)
    if deterministic is not None:
        method, score = deterministic
        metadata["method"] = method
        if answer_type == "numeric":
            metadata["core_contradiction"] = bool(
                _gold_answers(prediction)
                and all(
                    _core_numeric_conflict(
                        _predicted_answer(prediction),
                        answer,
                        str(prediction.get("question") or ""),
                    )
                    for answer in _gold_answers(prediction)
                )
            )
        return _uniform_metrics(score), metadata

    metadata["method"] = "local_claim_entailment"
    if judge is None:
        metadata["judge_status"] = "not_configured"
        return _empty_metrics(), metadata
    try:
        result = _validated_judge_result(judge(_judge_payload(prediction)))
    except (
        json.JSONDecodeError,
        KeyError,
        IndexError,
        OSError,
        TimeoutError,
        TypeError,
        ValueError,
        urllib.error.URLError,
    ) as exc:
        metadata.update(judge_status="error", error=str(exc))
        return _empty_metrics(), metadata

    return _core_extension_metrics(result, metadata)


def _core_extension_metrics(
    result: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, float | None], dict[str, Any]]:
    score = float(result["core_answer_supported"])
    if result["core_contradiction"]:
        score = 0.0
    metadata.update(
        judge_status="ok",
        core_answer_supported=result["core_answer_supported"],
        core_contradiction=result["core_contradiction"],
        supported_extension_count=result["supported_extension_count"],
        unsupported_extension_count=result["unsupported_extension_count"],
        has_unsupported_extension=result["unsupported_extension_count"] > 0,
    )
    return _uniform_metrics(score), metadata


def _answer_type(prediction: dict[str, Any]) -> str:
    metadata = dict(prediction.get("example_metadata") or {})
    family = str(metadata.get("dataset_family") or "").strip().lower()
    configured = str(prediction.get("answer_type") or "").strip().lower()
    if family == "hallucination_verification" or "verification" in configured:
        return "verification"
    gold_answers = _gold_answers(prediction)
    normalized_gold = {normalize_text(answer) for answer in gold_answers}
    if configured in {"boolean", "yes_no", "yes-no"} or (
        normalized_gold and normalized_gold <= set(_BOOLEAN_ALIASES)
    ):
        return "boolean"
    if normalized_gold and normalized_gold <= _UNANSWERABLE:
        return "unanswerable"
    if configured in _FORMULA_TYPES:
        return "formula"
    if configured in _NUMERIC_TYPES:
        return "numeric"
    if str(metadata.get("question_type") or "").strip().lower() == "metrics-generated":
        return "numeric"
    if configured in _LIST_TYPES:
        return "list"
    if configured == "date" or (
        gold_answers
        and all(_DATE_ONLY_RE.fullmatch(answer.strip()) for answer in gold_answers)
    ):
        return "date"
    return "free_text"


def _deterministic_score(
    prediction: dict[str, Any], answer_type: str
) -> tuple[str, float] | None:
    predicted = _predicted_answer(prediction)
    gold = _gold_answers(prediction)
    if not gold:
        return "deterministic_empty_gold", 0.0
    if answer_type == "boolean":
        predicted_value = _boolean_value(predicted)
        gold_values = {_boolean_value(answer) for answer in gold}
        score = float(predicted_value is not None and predicted_value in gold_values)
        return "deterministic_boolean", score
    if answer_type == "unanswerable":
        score = float(normalize_text(predicted) in _UNANSWERABLE)
        return "deterministic_unanswerable", score
    if answer_type == "numeric":
        score = float(numeric_tolerance_score(predicted, gold))
        question = str(prediction.get("question") or "")
        if score > 0 and all(
            _core_numeric_conflict(predicted, answer, question) for answer in gold
        ):
            return "deterministic_numeric", 0.0
        return "deterministic_numeric", score
    if answer_type == "formula":
        return "deterministic_formula", float(
            formula_normalized_match_score(predicted, gold)
        )
    if answer_type == "date":
        predicted_dates = {
            _normalize_date(value) for value in _DATE_RE.findall(predicted)
        }
        gold_dates = {
            _normalize_date(value)
            for answer in gold
            for value in _DATE_RE.findall(answer)
        }
        return "deterministic_date", _set_f1(predicted_dates, gold_dates)
    if answer_type == "list":
        return "deterministic_list", _list_f1(predicted, gold)
    return None


def _judge_payload(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": SEMANTIC_ANSWER_CONTRACT,
        "question": str(prediction.get("question") or ""),
        "gold_answers": _gold_answers(prediction),
        "gold_evidence": [
            str(item.get("span") or item.get("text") or "")
            for item in prediction.get("gold_evidence") or []
            if isinstance(item, dict)
        ],
        "predicted_answer": _predicted_answer(prediction),
    }


_EXTENSION_COUNT_FIELDS = (
    "supported_extension_count",
    "unsupported_extension_count",
)


def _validated_judge_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("Semantic judge result must be a JSON object.")
    expected_fields = {
        "core_answer_supported",
        *_EXTENSION_COUNT_FIELDS,
        "core_contradiction",
    }
    if set(result) != expected_fields:
        raise ValueError(
            "Semantic judge result fields do not match the prompt contract."
        )
    output: dict[str, Any] = {}
    if not isinstance(result.get("core_answer_supported"), bool):
        raise ValueError("Semantic judge core_answer_supported must be boolean.")
    output["core_answer_supported"] = result["core_answer_supported"]
    for field in _EXTENSION_COUNT_FIELDS:
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"Semantic judge field {field} must be a non-negative int."
            )
        output[field] = value
    if not isinstance(result.get("core_contradiction"), bool):
        raise ValueError("Semantic judge core_contradiction must be boolean.")
    output["core_contradiction"] = result["core_contradiction"]
    return output


def _parse_judge_json(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return json.loads(text)


def _judge_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _predicted_answer(prediction: dict[str, Any]) -> str:
    raw = prediction.get("answer_for_scoring", prediction.get("predicted_answer", ""))
    return extract_final_answer_text(str(raw or ""))


def _gold_answers(prediction: dict[str, Any]) -> list[str]:
    return [
        str(answer).strip()
        for answer in prediction.get("gold_answers") or []
        if str(answer or "").strip()
    ]


def _boolean_value(text: str) -> bool | None:
    normalized = normalize_text(text)
    first = normalized.split(" ", 1)[0] if normalized else ""
    return _BOOLEAN_ALIASES.get(first)


def _normalize_date(value: str) -> str:
    return re.sub(r"[\s,/]+", "-", str(value).strip().lower()).strip("-")


def _list_f1(predicted: str, gold_answers: list[str]) -> float:
    predicted_items = _list_items(predicted)
    if not predicted_items:
        return 0.0
    best = 0.0
    for gold in gold_answers:
        gold_items = _list_items(gold)
        if not gold_items:
            continue
        common = len(predicted_items & gold_items)
        precision = common / len(predicted_items)
        recall = common / len(gold_items)
        best = max(best, _harmonic_mean(precision, recall))
    return best


def _core_numeric_conflict(predicted: str, gold: str, question: str = "") -> bool:
    predicted_facts = _numeric_facts(predicted)
    gold_facts = _numeric_facts(gold)
    question_facts = _unambiguous_question_numeric_facts(question)
    for key in ("scale", "currency", "percent"):
        left = predicted_facts[key] or question_facts[key]
        right = gold_facts[key] or question_facts[key]
        if left != right and (left or right):
            return True
    return False


def _unambiguous_question_numeric_facts(text: str) -> dict[str, str]:
    lowered = str(text or "").lower()
    scales = {
        scale
        for scale in ("thousand", "million", "billion")
        if re.search(rf"\b{scale}s?\b", lowered)
    }
    currencies = {
        code
        for code, aliases in {
            "usd": ("usd", "us$", "$"),
            "eur": ("eur", "€"),
            "gbp": ("gbp", "£"),
            "jpy": ("jpy", "¥"),
        }.items()
        if any(alias in lowered for alias in aliases)
    }
    return {
        "scale": next(iter(scales)) if len(scales) == 1 else "",
        "currency": next(iter(currencies)) if len(currencies) == 1 else "",
        "percent": "percent" if "%" in lowered or "percent" in lowered else "",
    }


def _numeric_facts(text: str) -> dict[str, str]:
    lowered = str(text or "").lower()
    scale = next(
        (value for value in ("thousand", "million", "billion") if value in lowered),
        "",
    )
    currency = next(
        (
            code
            for code, aliases in {
                "usd": ("usd", "us$", "$"),
                "eur": ("eur", "€"),
                "gbp": ("gbp", "£"),
                "jpy": ("jpy", "¥"),
            }.items()
            if any(alias in lowered for alias in aliases)
        ),
        "",
    )
    return {
        "scale": scale,
        "currency": currency,
        "percent": "percent" if "%" in lowered or "percent" in lowered else "",
    }


def _set_f1(predicted: set[str], gold: set[str]) -> float:
    if not predicted or not gold:
        return 0.0
    common = len(predicted & gold)
    return _harmonic_mean(common / len(predicted), common / len(gold))


def _list_items(text: str) -> set[str]:
    return {
        normalize_text(item)
        for item in re.split(r"[,;\n]+", str(text or ""))
        if normalize_text(item)
    }


def _harmonic_mean(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _uniform_metrics(score: float) -> dict[str, float | None]:
    rounded = float(round_metric(score) or 0.0)
    return {
        "semantic_answer_precision": rounded,
        "semantic_answer_recall": rounded,
        "semantic_answer_f1": rounded,
    }


def _empty_metrics() -> dict[str, float | None]:
    return {
        "semantic_answer_precision": None,
        "semantic_answer_recall": None,
        "semantic_answer_f1": None,
    }


_JUDGE_SYSTEM_PROMPT = """/no_think
You are a benchmark evaluator, not an answer generator.
Compare the predicted answer with the question, gold answers, and gold evidence.
Decompose the prediction into one core answer and optional extensions. The core
answer may be a concise answer or a faithful paraphrase, and is supported only
when its material subject, relation, value, unit, time, scope, entity, and
polarity are entailed by a gold answer or gold evidence. Count each additional
supported sentence or proposition as a supported extension. Count each
relevant but unentailed additional sentence or proposition as an unsupported
extension. Unsupported extensions are excluded from answer credit and must not
make an otherwise supported core answer fail. A wrong core value, direction,
time, unit, scope, entity, or polarity is a core contradiction and is always
fatal. If there is no supported core answer, set core_answer_supported to false.
Return JSON only with exactly:
{"core_answer_supported": bool, "supported_extension_count": int,
 "unsupported_extension_count": int, "core_contradiction": bool}.
"""
