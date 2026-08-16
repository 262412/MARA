from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from ktem_contracts.conformance import TERMINAL_COMMIT_CONFORMANCE_VECTORS
from ktem_contracts.terminal_session_state import with_terminal_semantic_commit

from .query_task_state import QueryTaskState
from .query_terminal_outcome import (
    apply_operational_terminal_outcome,
    terminal_semantic_commit_for_message,
)


class TerminalOutcomeContractCompatibilityTest(unittest.TestCase):
    def test_operational_commit_matches_the_shared_neutral_contract(self) -> None:
        task = QueryTaskState(
            task_id="task-1",
            idempotency_key="request-1",
            conversation_id="session-1",
            prompt="Question",
            selected_file_ids=["file-1"],
            answer="Partial answer",
        )

        apply_operational_terminal_outcome(task, "timeout", "route_timeout")
        expected = next(
            vector["commit"]
            for vector in TERMINAL_COMMIT_CONFORMANCE_VECTORS
            if vector["name"] == "timeout_v3"
        )

        self.assertEqual(task.terminal_semantic_commit, expected)
        self.assertEqual(task.terminal_outcome, "timeout")

    def test_session_reader_consumes_the_shared_state_contract(self) -> None:
        commit = next(
            vector["commit"]
            for vector in TERMINAL_COMMIT_CONFORMANCE_VECTORS
            if vector["name"] == "answered_v3"
        )
        state = with_terminal_semantic_commit(
            {},
            message_index=2,
            commit=commit,
        )

        self.assertEqual(terminal_semantic_commit_for_message(state, 2), commit)

    def test_sidecar_terminal_contract_import_is_data_root_neutral(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment.pop("MARA_DESKTOP_DATA_DIR", None)
        environment["PYTHONPATH"] = os.pathsep.join([str(desktop_root), *sys.path])
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os, sys; import sidecar.query_terminal_outcome; "
                    "assert 'ktem' not in sys.modules; "
                    "assert 'MARA_DESKTOP_DATA_DIR' not in os.environ"
                ),
            ],
            cwd=desktop_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
