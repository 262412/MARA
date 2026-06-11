from __future__ import annotations

from typing import Callable

_ROUTE_LABELS = {
    "direct": "Direct",
    "doc_text": "Document",
    "doc_page_image": "Visual Page",
    "doc_element": "Element",
    "graph_global": "Graph",
    "hybrid": "Hybrid",
    "abstain": "Abstain",
}


def print_docqa_response(response, echo_text: Callable[[str], None]) -> None:
    echo_text(f"Conversation: {response.conversation_id}")
    if response.active_file_name:
        page_suffix = f" | page {response.page_number}" if response.page_number else ""
        echo_text(f"Active file: {response.active_file_name}{page_suffix}")
    echo_text("")
    echo_text(response.answer)
    _print_controller_summary(response, echo_text)
    if response.references_text:
        echo_text("")
        echo_text("Evidence:")
        echo_text(response.references_text)


def _print_controller_summary(response, echo_text: Callable[[str], None]) -> None:
    route_decision = _mapping_value(response, "route_decision")
    retrieve_decision = _mapping_value(response, "retrieve_decision")
    verify_decision = _mapping_value(response, "verify_decision")
    evidence_bundle = _mapping_value(response, "evidence_bundle")
    if not any([route_decision, retrieve_decision, verify_decision, evidence_bundle]):
        return

    echo_text("")
    route = str(route_decision.get("route") or "").strip()
    if route:
        echo_text(f"Route: {_route_label(route)}")
    retrieval_status = str(retrieve_decision.get("status") or "").strip()
    if retrieval_status:
        echo_text(f"Retrieval: {retrieval_status}")
    verification_status = str(verify_decision.get("status") or "").strip()
    if verification_status:
        action = str(verify_decision.get("action") or "").strip()
        suffix = f" ({action})" if action else ""
        echo_text(f"Verification: {verification_status}{suffix}")
    modalities = _modalities_from_bundle(evidence_bundle)
    if modalities:
        echo_text(f"Modalities: {', '.join(modalities)}")


def _mapping_value(response, key):
    value = getattr(response, key, None)
    return value if isinstance(value, dict) else {}


def _route_label(route: str) -> str:
    return _ROUTE_LABELS.get(route, route.replace("_", " ").title())


def _modalities_from_bundle(evidence_bundle):
    modalities = []
    for item in evidence_bundle.get("items") or []:
        if not isinstance(item, dict):
            continue
        modality = str(item.get("modality") or "").strip()
        if modality and modality not in modalities:
            modalities.append(modality)
    return modalities
