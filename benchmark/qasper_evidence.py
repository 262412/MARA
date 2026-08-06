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
    matches = _qasper_evidence_match_count(
        sorted(predicted_set),
        sorted(gold_set),
    )
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
    gold_match = [-1] * len(gold_evidence)

    def augment(predicted_index: int, seen: set[int]) -> bool:
        predicted = predicted_evidence[predicted_index]
        for gold_index, gold in enumerate(gold_evidence):
            if gold_index in seen or not _qasper_evidence_matches(predicted, gold):
                continue
            seen.add(gold_index)
            previous = gold_match[gold_index]
            if previous == -1 or augment(previous, seen):
                gold_match[gold_index] = predicted_index
                return True
        return False

    return sum(
        int(augment(predicted_index, set()))
        for predicted_index in range(len(predicted_evidence))
    )


def _qasper_evidence_matches(predicted: str, gold: str) -> bool:
    if predicted == gold:
        return True
    if predicted in gold or gold in predicted:
        return True
    return token_f1_score(predicted, [gold]) >= 0.5
