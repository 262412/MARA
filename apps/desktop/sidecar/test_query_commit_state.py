from __future__ import annotations

import unittest
from copy import deepcopy
from types import SimpleNamespace

from .application import DesktopApplicationService
from .query_terminal_outcome import (
    TERMINAL_SESSION_STATE_CONTRACT,
    TERMINAL_SESSION_STATE_KEY,
    _with_projection_hash,
)


class DesktopQueryCommitStateTest(unittest.TestCase):
    def test_committed_turn_is_recovered_without_another_model_call(self) -> None:
        runtime = CommitRuntime()
        service = DesktopApplicationService(
            collect_files=lambda: [{"file_id": "file-1", "name": "paper.pdf"}],
            create_runtime=lambda: runtime,
            create_query_request=lambda **values: SimpleNamespace(**values),
        )

        updates = list(
            service.stream_query(
                "session-1",
                "Question",
                ["file-1"],
                turn_id="turn-stable-1",
            )
        )
        recovered = service.recover_committed_turn(
            "session-1",
            "turn-stable-1",
        )

        self.assertTrue(updates[-1]["final"])
        self.assertEqual(updates[-1]["terminal_outcome"], "answered")
        self.assertEqual(
            updates[-1]["terminal_semantic_commit"]["semantic_answer"],
            "Committed answer",
        )
        assert recovered is not None
        self.assertEqual(recovered["answer"], "Committed answer")
        self.assertEqual(recovered["terminal_outcome"], "answered")
        recovered_commit = recovered["terminal_semantic_commit"]
        assert isinstance(recovered_commit, dict)
        self.assertEqual(
            recovered_commit["semantic_answer"],
            "Committed answer",
        )
        self.assertEqual(runtime.stream_calls, 1)
        self.assertFalse(runtime.session.state["app"]["regen"])


class CommitRuntime:
    def __init__(self) -> None:
        self.session = SimpleNamespace(
            conversation_id="session-1",
            state={"app": {"regen": False}},
            messages=[],
        )
        self.stream_calls = 0

    def load_session(self, _conversation_id):
        return self.session

    def stream_turn(self, request):
        self.stream_calls += 1
        self.session.state = request.state
        self.session.messages.append((request.prompt, "Committed answer"))
        commit = _answered_terminal_commit("Committed answer")
        state = deepcopy(self.session.state)
        state[TERMINAL_SESSION_STATE_KEY] = {
            "contract_id": TERMINAL_SESSION_STATE_CONTRACT,
            "commits": {"0": commit},
        }
        self.session.state = state
        yield SimpleNamespace(
            answer="Committed answer",
            event={},
            response=SimpleNamespace(
                answer="Committed answer",
                evidence_bundle={},
                evidence_metadata={},
                engine_terminal_commit=commit,
                terminal_semantic_commit=commit,
            ),
        )


def _answered_terminal_commit(answer: str) -> dict[str, object]:
    return _with_projection_hash(
        {
            "contract_id": "terminal_semantic_commit.v3",
            "semantic_answer": answer,
            "presentation_answer": answer,
            "outcome": "answered",
            "outcome_reason": "",
            "answer_status": "answered",
            "verify_decision": {"status": "supported", "action": "return"},
            "guardrail_decision": {"status": "ok", "action": "return"},
            "authoritative_evidence": [],
            "citations": [],
            "state_version": 3,
        }
    )
