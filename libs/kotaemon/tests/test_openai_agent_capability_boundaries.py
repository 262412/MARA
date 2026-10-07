"""Finite unsupported-entry contracts; refusal does not establish feature parity."""

import asyncio
import warnings

import pytest

from . import test_openai_agent_contracts as agent_contracts

agent_runtime = agent_contracts.agent_runtime


@pytest.mark.parametrize(
    "method, alternative", [("chat", "achat"), ("stream_chat", "astream_chat")]
)
def test_sync_entry_in_running_loop_refuses_before_coroutine_or_side_effects(
    agent_runtime, method, alternative
):
    create, requests, calls, _, debug = agent_runtime
    agent = create()

    async def run():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(RuntimeError, match=f"use await {alternative}"):
                getattr(agent, method)("must not dispatch")
            assert not caught
        assert not agent._active and agent.chat_history == []

    asyncio.run(run())
    assert requests == [] and calls == [] and debug.get_events() == []


@pytest.mark.parametrize(
    "method",
    [
        "create_task",
        "delete_task",
        "list_tasks",
        "get_task",
        "get_task_output",
        "get_upcoming_steps",
        "get_completed_steps",
        "run_step",
        "arun_step",
        "stream_step",
        "astream_step",
        "finalize_response",
        "undo_step",
    ],
)
def test_unprovided_agent_runner_entry_is_explicit_and_has_no_side_effects(
    agent_runtime, method
):
    create, requests, calls, _, debug = agent_runtime
    agent = create()
    with pytest.raises(AttributeError, match=method):
        getattr(agent, method)("unavailable-task")
    assert requests == [] and calls == [] and debug.get_events() == []
    assert not agent._active and agent.chat_history == []
