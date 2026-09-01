from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ktem.docqa.canonical_serialization import canonical_digest
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
)
from ktem.reasoning.mara_qasper_candidate_prompt import (
    _prioritized_candidate_prompt_evidence,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    prepare_qasper_canonical_records_with_trace,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qasper_stage2_10396653_7cd22_production_input_records.json"
)
EXAMPLE_ID = "7cd22ca9e107d2b13a7cc94252aaa9007976b338"
TARGET_EVIDENCE_ID = (
    "stable-chunk:3806ab5c7c7bee89c044213283a35d117"
    "fee31a5c12bda899ef2232d5fba6a6c"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10396653_stage2_production_input_is_frozen_exactly() -> None:
    payload = _fixture()
    source = payload["source"]
    digests = payload["digests"]
    records = payload["production_input_records"]

    assert payload["contract_id"] == (
        "qasper_stage2_production_input_characterization.v1"
    )
    assert source == {
        "job_id": "10396653",
        "code_sha": "1eb19b866cfdf130ae03939d4ef1f9f67ea3f2fe",
        "artifact_contract_id": "qasper_retrieval_index_artifact.v1",
        "artifact_digest": (
            "84a904ced2b37ca365cbb58ff1e67ad6284e5650d50491c2b57e0f1a947a0140"
        ),
        "serializer_identity": "canonical_json_utf8_v1",
        "example_id": EXAMPLE_ID,
        "route": "text_rag",
    }
    assert digests["raw_retrieval"] == (
        "b82eaf1003664d5bb0da82a264df6c73c6d88376dd5f07b1dff53403211edb18"
    )
    assert digests["ranking"] == (
        "cda500b3c637031a99774e90f24a9a58df3b7760ba2d5366cb939e1cf3bfd7d1"
    )
    assert digests["stage2_comparison"] == (
        "c3d83a65336fb102de91ef5b1a2a1617b99f15aa01607a6e521f650b1e7d54f3"
    )
    assert len(records) == payload["production_input_record_count"] == 8
    assert canonical_digest(records) == digests["production_input_records"] == (
        "f63a7fe09e1254e1e164180896d9dbaba3086396a86e977bf9dc16613cafb89d"
    )
    assert len({record["evidence_id"] for record in records}) == 8
    assert TARGET_EVIDENCE_ID in {record["evidence_id"] for record in records}


def test_proposition_bearing_spans_are_selected_before_the_record_limit() -> None:
    payload = _fixture()
    source = next(
        record
        for record in payload["production_input_records"]
        if record["evidence_id"] == TARGET_EVIDENCE_ID
    )
    record = {
        **source,
        "label": "E1",
        "text_start": 0,
        "candidate_source_text": source["text"],
        "candidate_source_text_start": 0,
        "canonical_start": None,
        "selectors": [],
    }

    prioritized = _prioritized_candidate_prompt_evidence(
        [record], payload["question"]
    )
    selected_refs = [
        selector["selector_id"] for selector in prioritized[0]["selectors"]
    ]
    trace = prioritized[0]["candidate_selector_projection_trace"]
    decisions = {
        decision["selector_id"]: decision for decision in trace["decisions"]
    }

    assert len(selected_refs) == 4
    assert {"E1:S5", "E1:S7"}.issubset(selected_refs)
    assert not {"E1:S16", "E1:S20"}.intersection(selected_refs)
    assert decisions["E1:S7"]["decision"] == (
        "selected_for_canonical_projection"
    )
    assert decisions["E1:S16"]["decision"] == "not_proposition_bearing"
    assert decisions["E1:S20"]["decision"] == "not_proposition_bearing"
    assert trace["proposition_bearing_selector_refs"] == [
        "E1:S5",
        "E1:S7",
        "E1:S8",
        "E1:S9",
        "E1:S10",
    ]

    canonical, _ = prepare_qasper_canonical_records_with_trace(
        payload["question"], prioritized
    )
    binding = candidate_evidence_set_binding(canonical, payload["question"])
    construction = binding["plan_construction_trace"]

    assert construction["binding_state"] == "relation_bound_support"
    assert binding["evidence_refs"] == ["E1:S5", "E1:S7"]
    assert construction["selected"]["support"]["span_refs"] == [
        "E1:S5",
        "E1:S7",
    ]
