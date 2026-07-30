from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .application import DesktopApplicationService
from .smoke_fixture import (
    GATE2_SMOKE_FILE_ID,
    GATE2_SMOKE_SESSION_ID,
    seed_smoke_fixture,
)


class Gate2SmokeFixtureTest(unittest.TestCase):
    def test_seeds_one_file_and_one_session_for_the_real_application_service(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"

            seed_smoke_fixture(data_root)
            seed_smoke_fixture(data_root)

            service = DesktopApplicationService()
            doctor = service.get_doctor()
            files = service.list_files()
            sessions = service.list_sessions()

            self.assertTrue(doctor["ok"])
            self.assertEqual(doctor["file_count"], 1)
            self.assertEqual(doctor["session_count"], 1)
            self.assertEqual(
                [record["file_id"] for record in files], [GATE2_SMOKE_FILE_ID]
            )
            self.assertNotIn("path", files[0])
            self.assertEqual(
                [record["conversation_id"] for record in sessions],
                [GATE2_SMOKE_SESSION_ID],
            )


if __name__ == "__main__":
    unittest.main()
