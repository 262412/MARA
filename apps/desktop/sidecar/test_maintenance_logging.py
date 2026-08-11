from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from .maintenance_logging import configure_maintenance_logging


class DesktopMaintenanceLoggingTest(unittest.TestCase):
    def test_index_failure_log_is_desktop_owned_and_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"
            handler = configure_maintenance_logging(data_root)
            logger = logging.getLogger("mara.desktop.index_tasks")
            try:
                logger.error(
                    "Index task failed task_id=%s error_code=%s error_type=%s",
                    "task-safe-id",
                    "embedding_unavailable",
                    "ConnectionError",
                )
                handler.flush()
                log_path = Path(handler.baseFilename)
                content = log_path.read_text(encoding="utf-8")
            finally:
                logger.removeHandler(handler)
                handler.close()

            self.assertTrue(log_path.is_relative_to(data_root / "logs"))
            self.assertIn("task-safe-id", content)
            self.assertIn("embedding_unavailable", content)
            self.assertIn("ConnectionError", content)
            self.assertNotIn("/private", content)
            self.assertNotIn("secret", content.casefold())


if __name__ == "__main__":
    unittest.main()
