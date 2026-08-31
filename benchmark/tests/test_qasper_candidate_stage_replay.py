from __future__ import annotations

from copy import deepcopy
from typing import Any, cast
from unittest.mock import patch

import pytest

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.tests.test_qasper_natural_semantic_pack_probe import (
    _CODE_SHA,
    _probe_prediction,
    _row,
)
from kotaemon.base import SystemMessage
from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_causal_transaction import _local_replay_prediction
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context
from scripts.slurm.qasper_natural_semantic_pack_runtime import _frozen_selected_records


def test_candidate_input_uses_frozen_pack_when_verifier_lineage_is_empty() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    verifier = cast(dict[str, Any], metadata["semantic_proposition_verifier"])
    lineage = cast(
        dict[str, Any],
        verifier.setdefault("semantic_data_lineage", {}),
    )
    lineage["source_packing"] = {
        "status": "not_run",
        "contract_id": "",
        "source_records": [],
        "records": [],
        "canonical_records": [],
        "selector_crosswalk": {},
        "dropped_count": 0,
        "truncated_count": 0,
    }
    snapshot = cast(
        dict[str, Any],
        cast(
            dict[str, Any],
            cast(dict[str, Any], metadata["qasper_canonical_semantic_pack"])[
                "source_packing_observation"
            ],
        )["source_input_snapshot"],
    )

    result = _probe_prediction(row, code_sha=_CODE_SHA)

    reference = next(
        stage
        for stage in result["causal_transaction_replay"]["reference_transaction"][
            "stages"
        ]
        if stage["stage_index"] == 3
    )
    assert reference["status"] == "complete"
    assert reference["payload"]["source_input_snapshot"] == snapshot
    assert (
        reference["payload"]["source_input_snapshot_digest"]
        == snapshot["snapshot_digest"]
    )


def test_candidate_replay_rejects_a_tampered_frozen_source_snapshot() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    pack = cast(dict[str, Any], metadata["qasper_canonical_semantic_pack"])
    source = cast(dict[str, Any], pack["source_packing_observation"])
    snapshot = cast(dict[str, Any], source["source_input_snapshot"])
    snapshot["max_context_length"] = 1024

    replay = candidate_replay_context(row)

    assert replay.observation["complete"] is False
    assert (
        "source_input_snapshot_digest_mismatch"
        in replay.observation["incompleteness_reasons"]
    )
    with pytest.raises(ValueError, match="frozen candidate-stage snapshot incomplete"):
        probe.freeze_natural_pack(
            str(row["question"]),
            route=str(row["route"]),
            example_id=str(row["example_id"]),
            replay=replay,
            code_sha=_CODE_SHA,
        )


def test_candidate_replay_uses_frozen_query_plan_not_terminal_projection() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    pack = cast(dict[str, Any], metadata["qasper_canonical_semantic_pack"])
    source = cast(dict[str, Any], pack["source_packing_observation"])
    snapshot = cast(dict[str, Any], source["source_input_snapshot"])
    frozen_query_plan = deepcopy(snapshot["query_plan"])
    metadata["query_plan"] = {"plan_id": "later-terminal-projection"}

    replay = candidate_replay_context(row)

    assert replay.query_plan == frozen_query_plan
    assert replay.observation["query_plan_source"] == "stage_input_snapshot"
    assert replay.observation["query_plan_digest"] == snapshot["query_plan_digest"]
    assert replay.observation["terminal_query_plan_digest"] == canonical_digest(
        metadata["query_plan"]
    )
    assert (
        "query_plan_does_not_match_stage_snapshot"
        not in replay.observation["incompleteness_reasons"]
    )


def test_candidate_replay_does_not_require_a_terminal_query_plan() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    metadata.pop("query_plan")

    result = _probe_prediction(row, code_sha=_CODE_SHA)

    assert result["status"] == "passed"
    replay = result["candidate_path_replay"]
    assert replay["query_plan_source"] == "stage_input_snapshot"
    assert replay["terminal_query_plan_digest"] == canonical_digest({})


def test_complete_frozen_request_bypasses_fallback_token_budget_decision() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)

    with patch(
        "ktem.reasoning.mara_qasper_candidate_request.fit_candidate_request",
        side_effect=AssertionError("fallback request fitting must not run"),
    ):
        context = probe.freeze_natural_pack(
            str(row["question"]),
            route=str(row["route"]),
            example_id=str(row["example_id"]),
            replay=replay,
            code_sha=_CODE_SHA,
        )

    local = context.candidate_generation
    frozen_fields = (
        "tokenizer_identity",
        "tokenizer_method",
        "tokenizer_exact",
        "tokenizer_endpoint",
        "estimated_input_tokens",
        "estimated_message_tokens",
        "estimated_schema_tokens",
        "candidate_input_token_budget",
        "max_model_len",
        "max_output_tokens",
        "token_headroom_tokens",
        "candidate_request_dropped_evidence_count",
        "request_dropped_evidence_count",
        "message_stack",
        "message_stack_digest",
        "response_schema_digest",
        "input_digest",
        "candidate_request_projection_trace",
    )
    assert {field: local[field] for field in frozen_fields} == {
        field: online[field] for field in frozen_fields
    }
    selected_ids = [
        decision["evidence_id"]
        for decision in local["candidate_request_projection_trace"]["decisions"]
        if decision["selected"] is True
    ]
    assert selected_ids == [record["evidence_id"] for record in context.frozen.records]


def test_candidate_replay_accepts_legacy_request_projection_without_atomic_fields() -> (
    None
):
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    candidates = [
        online,
        cast(
            dict[str, Any],
            cast(dict[str, Any], row["engine_terminal_evidence_bundle"])["metadata"][
                "qasper_candidate_generation"
            ],
        ),
    ]
    for candidate in candidates:
        projection = cast(
            dict[str, Any], candidate["candidate_request_projection_trace"]
        )
        for field in (
            "selected_record_ids",
            "selected_record_ids_digest",
            "final_message_stack",
            "final_message_stack_digest",
        ):
            projection.pop(field, None)

    replay = candidate_replay_context(row)

    assert replay.observation["complete"] is True
    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    assert context.candidate_generation["message_stack"] == online["message_stack"]
    assert (
        context.candidate_generation["message_stack_digest"]
        == online["message_stack_digest"]
    )
    result = _probe_prediction(row, code_sha=_CODE_SHA)
    assert result["checks"]["candidate_request_input_replayed"] is True
    assert (
        result["causal_transaction_replay"]["comparison"]["first_divergence"]["stage"]
        != "candidate_input"
    )


def test_candidate_replay_uses_frozen_messages_when_renderer_changes() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)

    with patch(
        "scripts.slurm.qasper_natural_semantic_pack_runtime.candidate_messages",
        return_value=[SystemMessage(content="changed renderer output")],
    ):
        context = probe.freeze_natural_pack(
            str(row["question"]),
            route=str(row["route"]),
            example_id=str(row["example_id"]),
            replay=replay,
            code_sha=_CODE_SHA,
        )

    assert context.candidate_generation["message_stack"] == online["message_stack"]
    assert (
        context.candidate_generation["message_stack_digest"]
        == online["message_stack_digest"]
    )
    assert (
        context.candidate_generation["candidate_prompt_projection_trace"]
        == online["candidate_prompt_projection_trace"]
    )


def test_frozen_request_preserves_duplicate_evidence_occurrences() -> None:
    records = [
        {"evidence_id": "duplicate", "occurrence": 1},
        {"evidence_id": "duplicate", "occurrence": 2},
        {"evidence_id": "other", "occurrence": 1},
    ]
    projection = {
        "selected_record_count": 2,
        "decisions": [
            {"evidence_id": "duplicate", "selected": True},
            {"evidence_id": "duplicate", "selected": False},
            {"evidence_id": "other", "selected": True},
        ],
    }

    selected = _frozen_selected_records(records, projection)

    assert selected == [records[0], records[2]]


def test_causal_replay_uses_frozen_online_candidate_stage() -> None:
    row = _row()
    online_metadata = cast(dict[str, Any], row["evidence_metadata"])
    online_pack = deepcopy(online_metadata["qasper_canonical_semantic_pack"])
    online_candidate = deepcopy(online_metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)
    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )
    context.bundle.metadata["qasper_canonical_semantic_pack"][
        "semantic_pack_digest"
    ] = "0" * 64
    context.candidate_generation["message_stack"] = [
        {"role": "system", "content": "current semantic projection"}
    ]

    prediction = _local_replay_prediction(
        row,
        context,
        preserve_frozen_semantic_projection=True,
    )

    assert prediction["evidence_metadata"]["qasper_canonical_semantic_pack"] == (
        online_pack
    )
    assert (
        prediction["_qasper_causal_replay_metadata"]["qasper_candidate_generation"][
            "message_stack"
        ]
        == online_candidate["message_stack"]
    )


def test_causal_replay_does_not_rehash_a_regenerated_candidate_request() -> None:
    row = _row()
    online_metadata = cast(dict[str, Any], row["evidence_metadata"])
    online_candidate = deepcopy(online_metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)
    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )
    context.candidate_generation["frozen_candidate_request_replay"] = {
        "status": "failed",
        "regenerated_message_stack": [
            {"index": 0, "role": "system", "content": "redo"}
        ],
    }

    prediction = _local_replay_prediction(
        row,
        context,
        preserve_frozen_semantic_projection=True,
    )

    assert (
        prediction["_qasper_causal_replay_metadata"]["qasper_candidate_generation"][
            "message_stack"
        ]
        == online_candidate["message_stack"]
    )
    assert (
        prediction["_qasper_causal_replay_metadata"]["qasper_candidate_generation"][
            "message_stack_digest"
        ]
        == online_candidate["message_stack_digest"]
    )


def test_incomplete_frozen_request_fails_closed_without_refitting() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    online.pop("estimated_input_tokens")
    replay = candidate_replay_context(row)

    with pytest.raises(ValueError, match="frozen candidate request incomplete"):
        probe.freeze_natural_pack(
            str(row["question"]),
            route=str(row["route"]),
            example_id=str(row["example_id"]),
            replay=replay,
            code_sha=_CODE_SHA,
        )


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("estimated_input_tokens", "candidate_token_measurement_incomplete"),
        ("candidate_input_token_budget", "candidate_token_budget_incomplete"),
        (
            "request_dropped_evidence_count",
            "candidate_total_request_drop_observation_missing",
        ),
    ],
)
def test_candidate_replay_rejects_incoherent_frozen_request_measurements(
    field: str,
    reason: str,
) -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    if field == "request_dropped_evidence_count":
        online[field] = None
    else:
        online[field] = int(online[field]) + 1

    replay = candidate_replay_context(row)

    assert replay.online_candidate_request["complete"] is False
    assert reason in replay.observation["incompleteness_reasons"]


def test_candidate_replay_rejects_a_frozen_request_over_its_token_budget() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    overflow = int(online["candidate_input_token_budget"])
    online["estimated_input_tokens"] = int(online["estimated_input_tokens"]) + overflow
    online["estimated_message_tokens"] = (
        int(online["estimated_message_tokens"]) + overflow
    )

    replay = candidate_replay_context(row)

    assert replay.online_candidate_request["complete"] is False
    assert (
        "candidate_token_budget_exceeded"
        in replay.observation["incompleteness_reasons"]
    )


def test_candidate_replay_rejects_changed_frozen_selected_record_identity() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    projection = cast(dict[str, Any], online["candidate_request_projection_trace"])
    decisions = cast(list[dict[str, Any]], projection["decisions"])
    decisions[0]["evidence_id"] = "changed-after-candidate-stage"
    projection["decisions_digest"] = canonical_digest(decisions)
    replay = candidate_replay_context(row)

    with pytest.raises(
        ValueError,
        match="frozen candidate request record identity mismatch",
    ):
        probe.freeze_natural_pack(
            str(row["question"]),
            route=str(row["route"]),
            example_id=str(row["example_id"]),
            replay=replay,
            code_sha=_CODE_SHA,
        )


def test_candidate_replay_keeps_internal_and_benchmark_routes_distinct() -> None:
    row = _row()
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    online = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    pack = cast(dict[str, Any], metadata["qasper_canonical_semantic_pack"])
    source = cast(dict[str, Any], pack["source_packing_observation"])
    snapshot = cast(dict[str, Any], source["source_input_snapshot"])
    snapshot["route"] = "doc_text"
    snapshot["snapshot_digest"] = canonical_digest(
        {key: value for key, value in snapshot.items() if key != "snapshot_digest"}
    )
    online["route"] = "doc_text"
    online["internal_route"] = "doc_text"
    online["benchmark_route_id"] = str(row["route"])
    online["input_digest"] = canonical_digest(
        {
            "messages": online["message_stack"],
            "response_schema_digest": online["response_schema_digest"],
            "seed": online["effective_seed"],
            "route": "doc_text",
            "benchmark_route_id": row["route"],
        }
    )
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    local_snapshot = context.bundle.metadata["qasper_canonical_semantic_pack"][
        "source_packing_observation"
    ]["source_input_snapshot"]
    assert context.candidate_generation["route"] == "doc_text"
    assert context.candidate_generation["internal_route"] == "doc_text"
    assert context.candidate_generation["benchmark_route_id"] == row["route"]
    assert context.candidate_generation["input_digest"] == online["input_digest"]
    assert local_snapshot["route"] == "doc_text"
    assert local_snapshot["snapshot_digest"] == snapshot["snapshot_digest"]


def test_candidate_replay_records_the_frozen_canonical_pack_identity() -> None:
    row = _row()
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    pack = context.bundle.metadata["qasper_canonical_semantic_pack"]
    assert (
        context.candidate_generation["evidence_pack_digest"]
        == (pack["semantic_pack_digest"])
    )
    assert (
        context.candidate_generation["canonical_semantic_pack_contract_id"]
        == (pack["contract_id"])
    )
    assert (
        context.candidate_generation["canonical_semantic_pack_digest"]
        == (pack["semantic_pack_digest"])
    )
    assert (
        context.candidate_generation["canonical_span_universe_digest"]
        == (pack["span_universe_digest"])
    )
    assert (
        context.candidate_generation["canonical_pack_candidate_transaction_id"]
        == pack["candidate_transaction_id"]
    )
