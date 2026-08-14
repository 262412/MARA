from __future__ import annotations

import unittest

from .query_task_state import QueryTaskState
from .query_terminal_outcome import (
    apply_operational_terminal_outcome,
    terminal_commit_projection_present,
    terminal_semantic_commit_for_message,
)


class TerminalOutcomeContractCompatibilityTest(unittest.TestCase):
    def test_operational_commit_matches_the_runtime_contract(self) -> None:
        from ktem.docqa.execution_contracts import ABSTAIN_MESSAGE
        from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

        task = QueryTaskState(
            task_id="task-1",
            idempotency_key="request-1",
            conversation_id="session-1",
            prompt="Question",
            selected_file_ids=["file-1"],
            answer="Partial answer",
        )

        apply_operational_terminal_outcome(task, "timeout", "route_timeout")
        expected = build_terminal_semantic_commit(
            ABSTAIN_MESSAGE,
            {"status": "timeout", "action": "error", "reason": "route_timeout"},
            {"status": "timeout", "action": "error", "reason": "route_timeout"},
            {"items": [], "metadata": {}},
            outcome="timeout",
            outcome_reason="route_timeout",
            presentation_answer="Partial answer",
        ).as_dict()

        self.assertEqual(task.terminal_semantic_commit, expected)
        self.assertTrue(terminal_commit_projection_present(expected))

    def test_session_reader_accepts_the_runtime_state_contract(self) -> None:
        from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit
        from ktem.docqa.terminal_session_state import with_terminal_semantic_commit

        commit = build_terminal_semantic_commit(
            "Grounded answer",
            {"status": "supported", "action": "return"},
            {"status": "ok", "action": "return"},
            {"items": [], "metadata": {}},
        ).as_dict()
        state = with_terminal_semantic_commit(
            {},
            message_index=2,
            commit=commit,
        )

        self.assertEqual(terminal_semantic_commit_for_message(state, 2), commit)


if __name__ == "__main__":
    unittest.main()
