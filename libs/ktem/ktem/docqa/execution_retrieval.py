from __future__ import annotations

from typing import Any

from .controller import RetrieveDecision, evaluate_retrieval_quality
from .evidence import EvidenceBundle
from .execution_models import RetrieveFn
from .query_planning import ensure_request_query_plan
from .retrieval_rounds import retrieve_with_rounds
from .route_capabilities import route_switch_candidates
from .route_selection import ControllerDecision


def retrieve_and_evaluate(
    request: Any,
    decision: ControllerDecision,
    retrieve: RetrieveFn,
    *,
    max_rounds: int | None = None,
) -> tuple[EvidenceBundle, RetrieveDecision]:
    plan = ensure_request_query_plan(request)
    return retrieve_with_rounds(
        request,
        decision,
        retrieve,
        evaluate=evaluate_retrieval_quality,
        retry_poor=(
            decision.legacy_route == "doc_element"
            or not route_switch_candidates(request, decision.legacy_route)
        ),
        max_rounds=plan.max_retrieval_rounds if max_rounds is None else max_rounds,
    )
