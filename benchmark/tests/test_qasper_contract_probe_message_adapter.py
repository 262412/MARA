from __future__ import annotations

from typing import Any

import pytest


def test_controlled_auditor_fault_messages_serialize_with_real_kotaemon_adapter() -> (
    None
):
    from kotaemon.base import HumanMessage, SystemMessage
    from kotaemon.llms import ChatOpenAI
    from scripts.slurm.qasper_debug_contract_probe_runtime import (
        _controlled_audit_messages,
    )

    messages = [
        SystemMessage(content="system audit instruction"),
        HumanMessage(content="audit this proposal"),
    ]
    controlled = _controlled_audit_messages(
        messages,
        stage="semantic_entailment_audit",
        fault="semantic_auditor_rejection",
    )
    adapter = ChatOpenAI(
        api_key="local",
        base_url="http://127.0.0.1:1/v1",
        model="adapter-characterization",
        max_retries=0,
    )

    serialized = adapter.prepare_message(controlled)

    assert isinstance(controlled[-1], HumanMessage)
    assert [message["role"] for message in serialized] == ["system", "user", "user"]
    assert "CONTRACT PROBE CONTROLLED AUDITOR FAULT" in str(serialized[-1]["content"])


def test_auditor_attempt_is_recorded_before_message_serialization_failure() -> None:
    from kotaemon.base import HumanMessage, SystemMessage
    from scripts.slurm.qasper_debug_contract_probe_runtime import (
        ProviderIdentity,
        _RecordingChatModel,
    )

    class _SerializationFailure:
        def prepare_message(self, messages: object) -> list[dict[str, str]]:
            del messages
            raise AttributeError("forced adapter serialization failure")

        def __call__(self, messages: object, **kwargs: object) -> object:
            del messages, kwargs
            raise AssertionError("provider transport must not start")

    calls: list[dict[str, Any]] = []
    model = _RecordingChatModel(
        _SerializationFailure(),
        case_id="serialization_failure",
        calls=calls,
        provider_identity=ProviderIdentity(
            base_url="http://auditor.invalid/v1",
            model="independent-auditor",
            role="auditor",
        ),
        controlled_audit_fault="semantic_auditor_rejection",
    )

    with pytest.raises(AttributeError, match="forced adapter serialization failure"):
        model(
            [
                SystemMessage(content="system audit instruction"),
                HumanMessage(content="audit this proposal"),
            ],
            response_format={"json_schema": {"name": "semantic_entailment_audit"}},
        )

    assert len(calls) == 1
    attempt = calls[0]
    assert attempt["stage"] == "semantic_entailment_audit"
    assert attempt["provider_role"] == "auditor"
    assert attempt["transport_status"] == "failed_before_transport"
    assert attempt["failure_phase"] == "message_serialization"
    assert attempt["exception_type"] == "AttributeError"
    assert attempt["exception_message"] == "forced adapter serialization failure"
    assert attempt["request_digest"]
    assert attempt["response_digest"] == ""
    assert attempt["message_type_identities"] == [
        "kotaemon.base.schema.SystemMessage",
        "kotaemon.base.schema.HumanMessage",
        "kotaemon.base.schema.HumanMessage",
    ]
