from __future__ import annotations

from typing import Any, Callable

from ktem.docqa.evidence_text import extract_final_answer_text

from .metrics import is_abstention_answer, round_metric

OBSERVABILITY_COUNT_FIELDS = (
    "abstained",
    "true_abstention",
    "false_abstention",
    "has_unsupported_claim",
    "retry_count",
    "route_switch_count",
)


def prediction_verifier_observability(prediction: dict[str, Any]) -> dict[str, int]:
    metrics = dict(prediction.get("metrics") or {})
    abstained = _prediction_abstained(prediction, metrics)
    false_abstention = int(_metric_positive(metrics, "false_abstention"))
    unsupported_claim_count = _unsupported_claim_count(prediction, metrics)
    return {
        "abstained": abstained,
        "true_abstention": int(bool(abstained and not false_abstention)),
        "false_abstention": false_abstention,
        "unsupported_claim_count": unsupported_claim_count,
        "has_unsupported_claim": int(_has_unsupported_claim(prediction, metrics)),
        "retry_count": _control_event_count(prediction, _is_retry_event),
        "route_switch_count": _control_event_count(prediction, _is_route_switch_event),
    }


def verifier_observability_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, int | float | None]:
    observations = _observations(predictions)
    return _observation_summary(observations)


def route_verifier_observability_table(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for route in _ordered_routes(predictions):
        route_predictions = [
            prediction
            for prediction in predictions
            if str(prediction.get("route") or "") == route
        ]
        rows.append(
            {
                "dataset_name": dataset_name,
                "route": route,
                "num_predictions": len(route_predictions),
                **route_verifier_observability_fields(route_predictions),
            }
        )
    return rows


def route_verifier_observability_fields(
    predictions: list[dict[str, Any]],
) -> dict[str, int | float | None]:
    return _observation_summary(_observations(predictions))


def _observation_summary(
    observations: list[dict[str, int]],
) -> dict[str, int | float | None]:
    num_predictions = len(observations)
    num_abstention = _sum_observations(observations, "abstained")
    num_true_abstention = _sum_observations(observations, "true_abstention")
    num_false_abstention = _sum_observations(observations, "false_abstention")
    num_unsupported_claim = _sum_observations(observations, "has_unsupported_claim")
    total_unsupported_claim_count = _sum_observations(
        observations,
        "unsupported_claim_count",
    )
    num_retry = sum(1 for item in observations if item.get("retry_count", 0) > 0)
    total_retry_count = _sum_observations(observations, "retry_count")
    num_route_switch = sum(
        1 for item in observations if item.get("route_switch_count", 0) > 0
    )
    total_route_switch_count = _sum_observations(observations, "route_switch_count")
    return {
        "num_abstention": num_abstention,
        "num_true_abstention": num_true_abstention,
        "num_false_abstention": num_false_abstention,
        "num_unsupported_claim": num_unsupported_claim,
        "total_unsupported_claim_count": total_unsupported_claim_count,
        "num_retry": num_retry,
        "total_retry_count": total_retry_count,
        "num_route_switch": num_route_switch,
        "total_route_switch_count": total_route_switch_count,
        "true_abstention_rate": _rate(num_true_abstention, num_predictions),
        "false_abstention_rate": _rate(num_false_abstention, num_predictions),
        "unsupported_claim_rate": _rate(num_unsupported_claim, num_predictions),
        "retry_rate": _rate(num_retry, num_predictions),
        "route_switch_rate": _rate(num_route_switch, num_predictions),
    }


def _observations(predictions: list[dict[str, Any]]) -> list[dict[str, int]]:
    return [
        dict(prediction["verifier_observability"])
        if isinstance(prediction.get("verifier_observability"), dict)
        else prediction_verifier_observability(prediction)
        for prediction in predictions
    ]


def _sum_observations(observations: list[dict[str, int]], key: str) -> int:
    return sum(int(item.get(key, 0) or 0) for item in observations)


def _rate(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round_metric(count / total)


def _prediction_abstained(prediction: dict[str, Any], metrics: dict[str, Any]) -> int:
    if _metric_positive(metrics, "abstained"):
        return 1
    claim_verification = dict(prediction.get("claim_verification") or {})
    if bool(claim_verification.get("abstained")):
        return 1
    answer = extract_final_answer_text(str(prediction.get("predicted_answer") or ""))
    return int(is_abstention_answer(answer))


def _metric_positive(metrics: dict[str, Any], key: str) -> bool:
    try:
        return float(metrics.get(key) or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def _unsupported_claim_count(
    prediction: dict[str, Any],
    metrics: dict[str, Any],
) -> int:
    claims = []
    for section_name in ("verify_decision", "claim_verification"):
        section = dict(prediction.get(section_name) or {})
        claims.extend(_text_items(section.get("unsupported_claims")))
    metric_count = _int_metric(metrics, "unsupported_claim_count")
    return max(metric_count, len(_dedupe(claims)))


def _has_unsupported_claim(
    prediction: dict[str, Any],
    metrics: dict[str, Any],
) -> bool:
    verify_decision = dict(prediction.get("verify_decision") or {})
    status = str(verify_decision.get("status") or "").strip().lower()
    return (
        _unsupported_claim_count(prediction, metrics) > 0
        or _metric_positive(metrics, "unsupported_claim_rate")
        or status == "unsupported"
    )


def _int_metric(metrics: dict[str, Any], key: str) -> int:
    try:
        return int(float(metrics.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _control_event_count(
    prediction: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool],
) -> int:
    return sum(1 for event in _control_events(prediction) if predicate(event))


def _control_events(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for key in ("controller_trace", "agent_trace", "retrieval_trace"):
        events.extend(_dict_items(prediction.get(key)))
    workflow_plan = prediction.get("workflow_plan")
    if isinstance(workflow_plan, dict):
        events.extend(_dict_items(workflow_plan.get("steps")))
        events.extend(_dict_items(workflow_plan.get("events")))
    else:
        events.extend(_dict_items(workflow_plan))
    return events


def _is_retry_event(event: dict[str, Any]) -> bool:
    if _truthy(event.get("retry")) or _truthy(event.get("retried")):
        return True
    return "retry" in _event_text(event)


def _is_route_switch_event(event: dict[str, Any]) -> bool:
    from_route = str(event.get("from_route") or event.get("previous_route") or "")
    to_route = str(event.get("to_route") or event.get("next_route") or "")
    if from_route and to_route and from_route != to_route:
        return True
    text = _event_text(event)
    return any(
        marker in text
        for marker in ("route_switch", "switch_route", "route switch", "switch route")
    )


def _event_text(event: dict[str, Any]) -> str:
    values = [
        str(value).strip().lower()
        for key, value in event.items()
        if key not in {"retry", "retried"} and isinstance(value, (str, int, float))
    ]
    return " ".join(value for value in values if value)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _text_items(value: Any) -> list[str]:
    return [str(item).strip() for item in value or [] if str(item or "").strip()]


def _dedupe(values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        if value not in items:
            items.append(value)
    return items


def _ordered_routes(predictions: list[dict[str, Any]]) -> list[str]:
    routes: list[str] = []
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        if route and route not in routes:
            routes.append(route)
    return routes
