from __future__ import annotations

import unittest
from copy import deepcopy
from types import SimpleNamespace

from ktem_contracts.conformance import TERMINAL_COMMIT_CONFORMANCE_VECTORS
from ktem_contracts.terminal_semantic_commit import with_projection_hash
from ktem_contracts.terminal_session_state import with_terminal_semantic_commit

from .application import DesktopApplicationService


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
        assert recovered is not None
        self.assertEqual(recovered["answer"], "Committed answer")
        self.assertEqual(recovered["terminal_outcome"], "answered")
        recovered_commit = recovered["terminal_semantic_commit"]
        assert isinstance(recovered_commit, dict)
        self.assertEqual(recovered_commit["semantic_answer"], "Committed answer")
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
        commit = deepcopy(
            next(
                vector["commit"]
                for vector in TERMINAL_COMMIT_CONFORMANCE_VECTORS
                if vector["name"] == "answered_v3"
            )
        )
        commit["presentation_answer"] = "Committed answer"
        commit["semantic_answer"] = "Committed answer"
        commit = with_projection_hash(
            {key: value for key, value in commit.items() if key != "projection_hash"}
        )
        self.session.state = with_terminal_semantic_commit(
            self.session.state,
            message_index=0,
            commit=commit,
        )
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
