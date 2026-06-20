from __future__ import annotations

from .metrics import normalize_text, token_f1_score


def qasper_paragraph_f1(
    predicted_evidence: list[str],
    gold_evidence: list[str],
) -> float:
    if not gold_evidence and not predicted_evidence:
        return 1.0
    if not gold_evidence or not predicted_evidence:
        return 0.0
    predicted_set = _normalized_evidence_set(predicted_evidence)
    gold_set = _normalized_evidence_set(gold_evidence)
    matches = _qasper_evidence_match_count(list(predicted_set), list(gold_set))
    if matches == 0:
        return 0.0
    precision = matches / len(predicted_set)
    recall = matches / len(gold_set)
    return 2 * precision * recall / (precision + recall)


def _normalized_evidence_set(values: list[str]) -> set[str]:
    return {text for text in (normalize_text(value) for value in values) if text}


def _qasper_evidence_match_count(
    predicted_evidence: list[str],
    gold_evidence: list[str],
) -> int:
    used_gold_indexes: set[int] = set()
    matches = 0
    for predicted in predicted_evidence:
        for index, gold in enumerate(gold_evidence):
            if index in used_gold_indexes:
                continue
            if _qasper_evidence_matches(predicted, gold):
                used_gold_indexes.add(index)
                matches += 1
                break
    return matches


def _qasper_evidence_matches(predicted: str, gold: str) -> bool:
    if predicted == gold:
        return True
    if predicted in gold or gold in predicted:
        return True
    return token_f1_score(predicted, [gold]) >= 0.5
