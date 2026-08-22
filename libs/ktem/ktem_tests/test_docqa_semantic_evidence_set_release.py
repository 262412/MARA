from __future__ import annotations

from typing import Any

from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.verification import verify_decision
from ktem_tests.test_docqa_semantic_evidence_set_authority import (
    _premises,
    _request,
    _semantic_verdict,
)


def test_semantic_verifier_cannot_bind_an_invented_quote() -> None:
    def invented_quote(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verdict = _semantic_verdict(*args, **kwargs)
        verdict["premises"][0]["quote"] = "This sentence was never retrieved."
        return verdict

    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_premises()),
        "yes",
        proposition_verifier=invented_quote,
    )

    assert decision.status != "supported"
    assert decision.verified_citations == []
    assert decision.typed_authority["state"] == "missing"


def test_semantic_verifier_requires_exact_canonical_offsets() -> None:
    items = _premises()
    items[0]["canonical_start"] = 100
    items[1]["canonical_start"] = 1000

    def canonical_verdict(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verdict = _semantic_verdict(*args, **kwargs)
        for premise, item in zip(verdict["premises"], items):
            premise["canonical_start"] = item["canonical_start"] + premise["span_start"]
            premise["canonical_end"] = item["canonical_start"] + premise["span_end"]
        return verdict

    supported = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "yes",
        proposition_verifier=canonical_verdict,
    )
    assert supported.status == "supported"

    def shifted_offset(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verdict = canonical_verdict(*args, **kwargs)
        verdict["premises"][0]["canonical_start"] += 1
        return verdict

    bundle = EvidenceBundle(route="doc_text", items=items)
    rejected = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
        proposition_verifier=shifted_offset,
    )

    assert rejected.status != "supported"
    assert bundle.metadata["semantic_proposition_authority"]["reason"] == (
        "semantic_premise_canonical_offset_unbound"
    )


def test_qasper_release_rejects_a_verifier_that_hides_nonrelease_audit_mode() -> None:
    request = _request()
    request.origin = "benchmark"
    request.verification_domain = "qasper"
    bundle = EvidenceBundle(route="doc_text", items=_premises())

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
        proposition_verifier=_semantic_verdict,
    )

    assert decision.status != "supported"
    assert bundle.metadata["semantic_proposition_authority"]["reason"] == (
        "semantic_release_mode_binding_invalid"
    )
