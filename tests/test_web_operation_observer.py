"""The harness observes original calls without replacing results or errors."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def observer_module():
    path = Path(__file__).parent / "browser" / "web_operation_observer.py"
    spec = importlib.util.spec_from_file_location("owned_observer_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(module, *, error=None):
    calls = []
    manager = SimpleNamespace(
        selected_group_id=SimpleNamespace(_id=1),
        group_list_state=SimpleNamespace(_id=2),
    )
    chat = SimpleNamespace(
        _app=SimpleNamespace(_index_1=manager), file_index=SimpleNamespace(id=1)
    )
    fn = SimpleNamespace(_id=7, name="set_group_id_selector", outputs=[])
    prediction = [['["file-id"]'], "select", {"selected": "chat-tab"}]

    async def call_function(block_fn, processed_input, requests=None, event_id=None):
        calls.append((event_id, list(processed_input)))
        if error:
            raise error
        return {"prediction": prediction}

    async def process_api(block_fn, inputs, state, request=None, event_id=None):
        return await blocks.call_function(
            block_fn, inputs, requests=request, event_id=event_id
        )

    blocks = SimpleNamespace(
        fns={7: fn},
        config={"dependencies": []},
        call_function=call_function,
        process_api=process_api,
    )
    observed_contexts = []
    barriers = SimpleNamespace(
        observe=lambda *args: observed_contexts.append(module.current_operation.get())
    )
    records = module.bind_operation_observer(blocks, chat, barriers)
    return blocks, records, calls, observed_contexts, prediction


def test_observer_keeps_request_identity_result_and_actual_group_state():
    module = observer_module()
    blocks, records, calls, contexts, prediction = fixture(module)
    state = {1: "stable-group", 2: [{"id": "stable-group"}]}
    request = SimpleNamespace(username="browser-owner", session_hash="owned-session")
    result = asyncio.run(
        blocks.process_api(7, ["stable-group", "owner"], state, request, "event-1")
    )
    assert result["prediction"] is prediction
    assert calls == [("event-1", ["stable-group", "owner"])]
    assert [record["phase"] for record in records] == ["call", "return", "postprocess"]
    assert records[-1]["selected_group_id"] == "stable-group"
    assert records[-1]["group_ids"] == ["stable-group"]
    assert contexts[0]["event_id"] == "event-1"
    assert contexts[0]["username"] == "browser-owner"
    assert module.current_operation.get() == {}


def test_observer_propagates_original_error_and_resets_context():
    module = observer_module()
    error = ValueError("owned failure")
    blocks, records, calls, contexts, _ = fixture(module, error=error)
    with pytest.raises(ValueError) as caught:
        asyncio.run(blocks.call_function(7, [None, "owner"], event_id="failed-event"))
    assert caught.value is error
    assert calls == [("failed-event", [None, "owner"])]
    assert records[-1]["error"] == "ValueError"
    assert contexts[0]["event_id"] == "failed-event"
    assert module.current_operation.get() == {}
