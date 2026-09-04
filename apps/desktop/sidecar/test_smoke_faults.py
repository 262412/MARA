from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .smoke_faults import query_smoke_fault_marker


class QuerySmokeFaultActivationTest(unittest.TestCase):
    def test_marker_or_environment_alone_cannot_activate_fault(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            marker = data_root / "tmp" / "query-fault"
            marker.parent.mkdir()
            marker.write_text("fresh-token\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER": str(marker)},
                clear=True,
            ):
                self.assertIsNone(query_smoke_fault_marker(data_root))

            with patch.dict(
                os.environ,
                {
                    "MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER": str(marker),
                    "MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN": "fresh-token",
                    "MARA_DESKTOP_QUERY_SMOKE_MODE": "query_persistence",
                },
                clear=True,
            ):
                marker.write_text("stale-token\n", encoding="utf-8")
                self.assertIsNone(query_smoke_fault_marker(data_root))

    def test_explicit_fresh_smoke_marker_activates_fault(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            marker = data_root / "tmp" / "query-fault"
            marker.parent.mkdir()
            marker.write_text("fresh-token\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER": str(marker),
                    "MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN": "fresh-token",
                    "MARA_DESKTOP_QUERY_SMOKE_MODE": "query_persistence",
                },
                clear=True,
            ):
                self.assertEqual(query_smoke_fault_marker(data_root), marker.resolve())


if __name__ == "__main__":
    unittest.main()
