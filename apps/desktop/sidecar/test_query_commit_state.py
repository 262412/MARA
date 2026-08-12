from __future__ import annotations

import unittest
from types import SimpleNamespace

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
        self.assertEqual(recovered, {"answer": "Committed answer", "citations": []})
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
        yield SimpleNamespace(
            answer="Committed answer",
            event={},
            response=SimpleNamespace(
                answer="Committed answer",
                evidence_bundle={},
                evidence_metadata={},
            ),
        )
