from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_aggregation import aggregate_answer_claims
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.graph_evidence import _graph_locator_items
from ktem.docqa.retrieval_adequacy import retrieval_adequacy_issue
from ktem.docqa.verification import verify_decision


def test_boolean_conflicting_evidence_is_ambiguous():
    request = DocQARequest(
        prompt="Did the authors release the code?",
        task_type="boolean",
        verification_mode="strict",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "support",
                    "source_id": "paper",
                    "text": "The authors released the code.",
                },
                {
                    "evidence_id": "conflict",
                    "source_id": "paper",
                    "text": "The authors did not release the code.",
                },
            ]
        },
    )

    decision = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        "yes",
    )

    assert decision.status == "unknown"
    assert decision.claim_results[0]["supporting_evidence_ids"]
    assert decision.claim_results[0]["contradicting_evidence_ids"]


def test_graph_source_backref_strips_marker():
    item = {
        "evidence_id": "graph-node",
        "element_id": "node",
        "source_backrefs": ["paper#source"],
    }

    projected = _graph_locator_items(item, expand=False)

    assert projected[0]["source_id"] == "paper"
    assert projected[0]["page_label"] == ""


def test_span_id_does_not_require_redundant_evidence_level():
    identity = identity_of(
        {
            "runtime_source_id": "paper",
            "span_id": "span-7",
            "element_id": "paragraph-2",
        }
    )

    assert identity.kind == "span"
    assert identity.source_id == "paper"
    assert identity.local_id == "span-7"


def test_identity_key_escapes_separator_collisions():
    left = identity_of({"source_id": "a:b", "cell_id": "c"})
    right = identity_of({"source_id": "a", "cell_id": "b:c"})

    assert left != right
    assert left.key != right.key


def test_finance_adequacy_rejects_any_missing_required_field():
    issue = retrieval_adequacy_issue(
        "Calculate the quick ratio.",
        {
            "evidence": [
                {
                    "source_id": "report",
                    "page_label": "5",
                    "text": "Current assets were 100.",
                }
            ]
        },
        domain="finance",
    )

    assert "current liabilities" in issue
    assert "inventories" in issue


def test_claim_aggregation_uses_typed_fact_key_not_token_jaccard():
    answer, trace = aggregate_answer_claims(
        "In fiscal 2022, consolidated revenue rose to $10 million. [1]\n"
        "Revenue increased to $10 million for the consolidated group in 2022. [2]"
    )

    assert answer.count("$10 million") == 1
    assert trace["duplicate_claim_count"] == 1
    assert trace["claim_key_contract"] == "typed_claim_key.v1"


def test_claim_aggregation_keeps_different_scope():
    answer, trace = aggregate_answer_claims(
        "Consolidated revenue increased to $10 million in 2022. [1]\n"
        "European revenue increased to $10 million in 2022. [2]"
    )

    assert answer.count("$10 million") == 2
    assert trace["duplicate_claim_count"] == 0
