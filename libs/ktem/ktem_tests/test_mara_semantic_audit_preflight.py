from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import ktem.reasoning.mara_semantic_proposition_stages as stages
from ktem.docqa.question_proposition import build_question_proposition
from ktem.reasoning.mara_semantic_audit_preflight import audit_preflight_failure_reason
from ktem.reasoning.mara_semantic_entailment_audit import (
    semantic_entailment_audit_response_format,
)
from ktem.reasoning.mara_semantic_proposition_stages import (
    audit_diagnostics,
    audit_stage,
)
from ktem.reasoning.mara_semantic_transaction_support import (
    bind_semantic_runtime_fields,
)


class _CountingLLM:
    model_name = "semantic-auditor"

    def __init__(self, response: str | None = None) -> None:
        self.response = response
        self.calls = 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        if self.response is None:
            raise AssertionError("pre-audit validation must stop before the provider")
        return SimpleNamespace(text=self.response)


def _slot_evidence(*slots: str) -> dict[str, dict[str, Any]]:
    return {
        slot: {
            "text": slot,
            "span_start": index,
            "span_end": index + len(slot),
            "clause_ref": "C1",
            "clause_start": 0,
            "clause_end": 32,
            "evidence_ref": f"P1:{slot}",
        }
        for index, slot in enumerate(slots)
    }


def _audit_response() -> str:
    return json.dumps(
        {
            "premise_checks": {
                "P1": {
                    "fragment_entailed": True,
                    "scope_consistent": True,
                    "evidence_relation_valid": True,
                    "proposition_slot_checks": {
                        "actor": {
                            "binding_valid": True,
                            "evidence_ref": "P1:actor",
                        },
                        "predicate": {
                            "binding_valid": True,
                            "evidence_ref": "P1:predicate",
                        },
                    },
                }
            },
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "actor_consistent": True,
                "predicate_consistent": True,
                "object_consistent": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def test_slot_evidence_mismatch_is_pre_audit_and_skips_schema_and_provider(
    monkeypatch: Any,
) -> None:
    def forbidden_schema(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the auditor schema must not be built")

    monkeypatch.setattr(
        stages,
        "semantic_entailment_audit_response_format",
        forbidden_schema,
    )
    llm = _CountingLLM()

    stage = audit_stage(
        llm,
        "audit prompt",
        1,
        seed=17,
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence={"P1": _slot_evidence("actor")},
    )

    assert stage.value is None
    assert stage.failure_reason == "pre_audit_slot_evidence_mismatch"
    assert stage.provider_failure_reason == ""
    assert stage.call_count == 0
    assert llm.calls == 0
    diagnostics = audit_diagnostics(stage, model=llm.model_name)
    assert diagnostics["audit_status"] == "not_started"
    assert diagnostics["audit_execution_status"] == "not_started"
    assert diagnostics["audit_reason"] == "pre_audit_slot_evidence_mismatch"


def test_pre_call_auditor_schema_failure_does_not_count_as_provider_call(
    monkeypatch: Any,
) -> None:
    def invalid_schema(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("schema validation failed")

    monkeypatch.setattr(
        stages,
        "semantic_entailment_audit_response_format",
        invalid_schema,
    )
    llm = _CountingLLM()
    stage = audit_stage(
        llm,
        "audit prompt",
        1,
        seed=17,
        premise_slot_expectations={"P1": ("actor",)},
        premise_slot_evidence={"P1": _slot_evidence("actor")},
    )

    assert stage.value is None
    assert stage.failure_reason == "pre_audit_schema_validation_failed"
    assert stage.provider_failure_reason == ""
    assert stage.call_count == 0
    assert llm.calls == 0
    assert audit_diagnostics(stage, model=llm.model_name)["audit_status"] == (
        "not_started"
    )


def test_malformed_slot_evidence_is_rejected_before_schema_build() -> None:
    llm = _CountingLLM()
    stage = audit_stage(
        llm,
        "audit prompt",
        1,
        seed=17,
        premise_slot_expectations={"P1": ("actor",)},
        premise_slot_evidence={"P1": {"actor": {}}},
    )

    assert stage.value is None
    assert stage.failure_reason == "pre_audit_slot_evidence_mismatch"
    assert stage.provider_failure_reason == ""
    assert stage.call_count == 0
    assert llm.calls == 0


def test_missing_fourth_slot_is_not_shrunk_or_promoted_to_bound() -> None:
    llm = _CountingLLM()
    stage = audit_stage(
        llm,
        "audit prompt",
        1,
        seed=17,
        premise_slot_expectations={
            "P1": ("actor", "predicate", "object", "quantifier")
        },
        premise_slot_evidence={"P1": _slot_evidence("actor", "predicate", "object")},
    )

    assert stage.value is None
    assert stage.failure_reason == "pre_audit_slot_evidence_mismatch"
    assert stage.provider_failure_reason == ""
    assert stage.call_count == 0
    assert llm.calls == 0


def test_audit_call_is_counted_after_provider_invocation_starts() -> None:
    llm = _CountingLLM(_audit_response())
    stage = audit_stage(
        llm,
        "audit prompt",
        1,
        seed=17,
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence={"P1": _slot_evidence("actor", "predicate")},
    )

    assert stage.value is not None
    assert stage.provider_failure_reason == ""
    assert stage.call_count == 1
    assert llm.calls == 1
    assert audit_diagnostics(stage, model=llm.model_name)["audit_status"] == ("parsed")


def test_frozen_projection_slot_metadata_skips_legacy_span_schema() -> None:
    frozen_span = {
        "text": "actor",
        "span_start": 0,
        "span_end": 5,
        "clause_ref": "C1",
        "clause_start": 0,
        "clause_end": 32,
        "evidence_ref": "E1:S1#semantic-slot:actor:0:5",
        "parent_selector_id": "E1:S1",
        "parent_span_start": 0,
        "parent_span_end": 32,
        "parent_text_digest": "parent-digest",
        "text_digest": "span-digest",
    }
    projection = SimpleNamespace(
        premises=({"binds_proposition_slots": ["actor"]},),
        audit_slot_evidence={"P1": {"actor": frozen_span}},
    )

    assert (
        audit_preflight_failure_reason(
            ("P1",),
            premise_slot_expectations={"P1": ("actor",)},
            premise_slot_evidence={"P1": {"actor": frozen_span}},
            canonical_plan_projection=projection,
        )
        == ""
    )


def test_frozen_projection_audit_view_matches_schema_contract() -> None:
    frozen_span = {
        "text": "actor",
        "span_start": 0,
        "span_end": 5,
        "clause_ref": "C1",
        "clause_start": 0,
        "clause_end": 32,
        "evidence_ref": "E1:S1#semantic-slot:actor:0:5",
        "parent_selector_id": "E1:S1",
        "parent_span_start": 0,
        "parent_span_end": 32,
        "parent_text_digest": "parent-digest",
        "text_digest": "span-digest",
    }
    audit_span = {
        field: frozen_span[field]
        for field in (
            "text",
            "span_start",
            "span_end",
            "clause_ref",
            "clause_start",
            "clause_end",
        )
    }
    audit_span["evidence_ref"] = "P1:actor"

    try:
        semantic_entailment_audit_response_format(
            ["P1"],
            premise_slot_expectations={"P1": ("actor",)},
            premise_slot_evidence={"P1": {"actor": frozen_span}},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("full frozen identity must not enter the audit schema")

    schema = semantic_entailment_audit_response_format(
        ["P1"],
        premise_slot_expectations={"P1": ("actor",)},
        premise_slot_evidence={"P1": {"actor": audit_span}},
    )
    evidence_schema = schema["json_schema"]["schema"]["properties"]["premise_checks"][
        "properties"
    ]["P1"]["properties"]["proposition_slot_checks"]["properties"]["actor"]
    assert evidence_schema["properties"]["evidence_ref"]["enum"] == ["P1:actor"]


def test_frozen_projection_bindings_are_not_recomputed_from_question() -> None:
    proposition = build_question_proposition("Does the model learn?")
    frozen = {"object": "frozen-object-binding"}
    projection = SimpleNamespace(
        plan_id="frozen-plan",
        plan_digest="frozen-plan",
        proof_mode="atomic_semantic",
        polarity_relation="proposition_support",
        premises=(
            {
                "binds_proposition_slots": ["object"],
                "proposition_slot_bindings": frozen,
                "evidence_relation": "proposition_support",
            },
        ),
        as_dict=lambda: {"plan_id": "frozen-plan"},
    )
    context = SimpleNamespace(
        proposition=proposition,
        proposition_resolution={},
        release_mode=True,
        auditor_relationship="distinct_model",
        semantic_pack_digest="pack",
        canonical_span_universe_digest="spans",
        candidate_transaction_id="transaction",
        canonical_plan_projection=projection,
    )
    value: dict[str, Any] = {
        "premises": [
            {
                "binds_proposition_slots": ["object"],
                "proposition_slot_bindings": {"object": "quote-derived"},
                "evidence_relation": "explicit_contradiction",
            }
        ],
        "verifier": {},
    }

    bind_semantic_runtime_fields(value, cast(Any, context))

    assert value["premises"][0]["proposition_slot_bindings"] == frozen
    assert value["premises"][0]["evidence_relation"] == "proposition_support"
