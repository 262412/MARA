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
    "retrieval_retry_count",
    "verifier_recovery_count",
    "route_switch_count",
)


def prediction_verifier_observability(prediction: dict[str, Any]) -> dict[str, int]:
    metrics = dict(prediction.get("metrics") or {})
    abstained = _prediction_abstained(prediction, metrics)
    false_abstention = int(_metric_positive(metrics, "false_abstention"))
    unsupported_claim_count = _unsupported_claim_count(prediction, metrics)
    observations = {
        "abstained": abstained,
        "true_abstention": int(bool(abstained and not false_abstention)),
        "false_abstention": false_abstention,
        "unsupported_claim_count": unsupported_claim_count,
        "has_unsupported_claim": int(_has_unsupported_claim(prediction, metrics)),
        "retry_count": _control_event_count(
            prediction,
            _is_retry_event,
            kind="retry",
        ),
        "route_switch_count": _control_event_count(
            prediction,
            _is_route_switch_event,
            kind="route_switch",
        ),
    }
    category_counts = _category_event_counts(prediction)
    if (
        category_counts["retrieval_retry_count"]
        or category_counts["verifier_recovery_count"]
    ):
        observations.update(category_counts)
    return observations


def verifier_observability_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = _observations(predictions)
    summary = _observation_summary(observations)
    summary.update(_observed_policy_fields(predictions))
    return summary


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
) -> dict[str, Any]:
    fields = _observation_summary(_observations(predictions))
    fields.update(_observed_policy_fields(predictions))
    return fields


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
    summary = {
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
    retrieval_retry_count = _sum_observations(
        observations,
        "retrieval_retry_count",
    )
    verifier_recovery_count = _sum_observations(
        observations,
        "verifier_recovery_count",
    )
    if retrieval_retry_count or verifier_recovery_count:
        summary.update(
            {
                "num_retrieval_retry": sum(
                    1
                    for item in observations
                    if item.get("retrieval_retry_count", 0) > 0
                ),
                "total_retrieval_retry_count": retrieval_retry_count,
                "num_verifier_recovery": sum(
                    1
                    for item in observations
                    if item.get("verifier_recovery_count", 0) > 0
                ),
                "total_verifier_recovery_count": verifier_recovery_count,
            }
        )
    return summary


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
    *,
    kind: str,
) -> int:
    seen: set[tuple[str, ...]] = set()
    count = 0
    for event in _control_events(prediction):
        if not predicate(event):
            continue
        key = _logical_control_event_key(event, kind=kind)
        if key in seen:
            continue
        seen.add(key)
        count += 1
    return count


def _category_event_counts(prediction: dict[str, Any]) -> dict[str, int]:
    events = _control_events(prediction)
    verifier_recovery_count = _control_event_count_from_events(
        events,
        _is_verifier_recovery_event,
        kind="verifier_recovery",
    )
    explicit_retrieval_retry_count = _control_event_count_from_events(
        events,
        _is_retrieval_retry_event,
        kind="retrieval_retry",
    )
    return {
        "retrieval_retry_count": max(
            explicit_retrieval_retry_count,
            _implicit_retrieval_retry_count(
                prediction,
                verifier_recovery_count=verifier_recovery_count,
            ),
        ),
        "verifier_recovery_count": verifier_recovery_count,
    }


def _implicit_retrieval_retry_count(
    prediction: dict[str, Any],
    *,
    verifier_recovery_count: int,
) -> int:
    rounds = 1
    metadata_values = [prediction.get("evidence_metadata")]
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        metadata_values.append(bundle.get("metadata"))
    for metadata in metadata_values:
        if not isinstance(metadata, dict):
            continue
        try:
            rounds = max(rounds, int(metadata.get("retrieval_rounds") or 1))
        except (TypeError, ValueError):
            continue
    return max(0, rounds - 1 - verifier_recovery_count)


def _control_event_count_from_events(
    events: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    *,
    kind: str,
) -> int:
    seen: set[tuple[str, ...]] = set()
    count = 0
    for event in events:
        if not predicate(event):
            continue
        key = _logical_control_event_key(event, kind=kind)
        if key in seen:
            continue
        seen.add(key)
        count += 1
    return count


def _logical_control_event_key(
    event: dict[str, Any],
    *,
    kind: str,
) -> tuple[str, ...]:
    attempt = _attempt_identity(event)
    event_id = _event_id(event, kind=kind)
    if event_id:
        return (kind, "event_id", event_id, *attempt)

    if kind == "route_switch":
        from_route = _route_value(
            event.get("from_route") or event.get("previous_route")
        )
        to_route = _route_value(event.get("to_route") or event.get("next_route"))
        if from_route or to_route:
            return (kind, "route", from_route, to_route, *attempt)
        return (kind, "marker", _route_switch_marker(event), *attempt)

    if kind == "verifier_recovery":
        return (
            kind,
            "recovery",
            _event_id(event, kind=kind),
            _normalized_event_value(event.get("verifier_recovery_attempt"))
            or _normalized_event_value(event.get("attempt")),
            _normalized_event_value(event.get("failure_type"))
            or _normalized_event_value(event.get("retry_reason")),
            _route_value(event.get("from_route") or event.get("route")),
            _route_value(event.get("to_route")),
        )
    return (
        kind,
        "retry",
        _retry_label(event),
        _route_value(event.get("route")),
        *attempt,
    )


def _event_id(event: dict[str, Any], *, kind: str) -> str:
    keys: tuple[str, ...] = (
        "event_id",
        "logical_event_id",
        "logical_transition_key",
        "transition_id",
    )
    if kind == "retry":
        keys += ("retry_id", "logical_retry_key", "retry_key")
    if kind == "verifier_recovery":
        keys += ("recovery_id", "logical_recovery_key", "recovery_key")
    for key in keys:
        value = _normalized_event_value(event.get(key))
        if value:
            return value
    return ""


def _attempt_identity(event: dict[str, Any]) -> tuple[str, ...]:
    identity: list[str] = []
    for key in (
        "attempt_id",
        "transition_attempt",
        "retry_attempt",
        "attempt",
        "attempt_number",
        "retry_index",
        "retry_count",
        "round_id",
        "retry_round",
        "round",
        "query_id",
        "slot_id",
        "request_id",
    ):
        value = _normalized_event_value(event.get(key))
        if value:
            identity.append(f"{key}={value}")
    return tuple(identity)


def _route_value(value: Any) -> str:
    return _normalized_event_value(value)


def _retry_label(event: dict[str, Any]) -> str:
    for key in (
        "retry_kind",
        "retry_reason",
        "action",
        "event",
        "operation",
        "reason",
    ):
        value = _normalized_event_value(event.get(key))
        if value:
            return value
    return "retry"


def _route_switch_marker(event: dict[str, Any]) -> str:
    text = _event_text(event)
    if any(
        marker in text
        for marker in ("route_switch", "switch_route", "route switch", "switch route")
    ):
        return "route_switch"
    return text or "route_switch"


def _normalized_event_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return str(value).strip().lower()
    return ""


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


def _is_verifier_recovery_event(event: dict[str, Any]) -> bool:
    if event.get("verifier_recovery_attempt") is not None:
        return True
    stage = _normalized_event_value(event.get("stage"))
    return bool(
        stage
        in {
            "verifier_recovery",
            "critic",
            "focused_retrieval",
            "evidence_rebind",
            "reverify",
        }
        and (
            "recovery" in _event_text(event)
            or event.get("failure_type")
            or event.get("retry_reason")
        )
    )


def _is_retrieval_retry_event(event: dict[str, Any]) -> bool:
    if _is_verifier_recovery_event(event):
        return False
    explicit = " ".join(
        _normalized_event_value(event.get(key))
        for key in ("retry_kind", "retry_reason", "action", "event", "operation")
    )
    return "retrieval" in explicit and "retry" in explicit


def _is_route_switch_event(event: dict[str, Any]) -> bool:
    from_route = str(event.get("from_route") or event.get("previous_route") or "")
    to_route = str(event.get("to_route") or event.get("next_route") or "")
    if from_route and to_route and from_route != to_route:
        return True
    labels = {
        _normalized_event_value(event.get(key)).replace(" ", "_")
        for key in ("stage", "event", "action", "operation")
    }
    return bool(
        labels
        & {
            "route_switch",
            "switch_route",
            "route_transition",
        }
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


def _observed_policy_fields(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    modes = _observed_values(predictions, "agent_mode")
    policies = _observed_values(predictions, "route_policy")
    fields: dict[str, Any] = {}
    if modes:
        fields["agent_modes"] = modes
    if policies:
        fields["route_policies"] = policies
    return fields


def _observed_values(predictions: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for prediction in predictions:
        value = str(prediction.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return values
