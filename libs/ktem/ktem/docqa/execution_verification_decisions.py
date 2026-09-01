from __future__ import annotations

from typing import Any

from .controller import VerifyDecision
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle


def evidence_only_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = _verification_mode(request)
    return VerifyDecision(
        mode=mode,
        status="not_required",
        reason="Evidence-only visual route did not invoke a VLM generator.",
        verified_citations=_bundle_citation_ids(bundle),
    )


def empty_answer_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = _verification_mode(request)
    return VerifyDecision(
        mode=mode,
        status="not_enough_evidence",
        reason=f"{mode.title()} verification found no final answer to verify.",
        action="abstain",
        verified_citations=_bundle_citation_ids(bundle),
    )


def _verification_mode(request: Any) -> str:
    mode = str(getattr(request, "verification_mode", None) or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"


def _bundle_citation_ids(bundle: EvidenceBundle) -> list[str]:
    return list(
        dict.fromkeys(
            identity_of(item).key for item in bundle.items if identity_of(item).key
        )
    )
