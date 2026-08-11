from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from .maintenance_logging import configure_maintenance_logging
from .server import _attach_query_maintenance_loggers


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

            self.assertTrue(log_path.is_relative_to(data_root.resolve() / "logs"))
            self.assertIn("task-safe-id", content)
            self.assertIn("embedding_unavailable", content)
            self.assertIn("ConnectionError", content)
            self.assertNotIn("/private", content)
            self.assertNotIn("secret", content.casefold())

    def test_query_failure_log_uses_same_restricted_handler_without_duplicates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"
            handler = configure_maintenance_logging(data_root)
            _attach_query_maintenance_loggers(handler)
            _attach_query_maintenance_loggers(handler)
            loggers = [
                logging.getLogger("mara.desktop.query_tasks"),
                logging.getLogger("mara.desktop.query_stream"),
            ]
            try:
                for logger in loggers:
                    self.assertEqual(logger.handlers.count(handler), 1)
                loggers[0].error(
                    "Query task failed task_id=%s error_code=%s stage=%s error_type=%s",
                    "query-safe-id",
                    "llm_unavailable",
                    "streaming",
                    "ConnectionError",
                )
                handler.flush()
                log_path = Path(handler.baseFilename)
                content = log_path.read_text(encoding="utf-8")
            finally:
                logging.getLogger("mara.desktop.index_tasks").removeHandler(handler)
                for logger in loggers:
                    logger.removeHandler(handler)
                    logger.propagate = True
                handler.close()

            self.assertTrue(log_path.is_relative_to(data_root.resolve() / "logs"))
            self.assertIn("query-safe-id", content)
            self.assertIn("llm_unavailable", content)
            self.assertIn("streaming", content)
            self.assertIn("ConnectionError", content)
            self.assertNotIn("/private", content)
            self.assertNotIn("secret", content.casefold())


if __name__ == "__main__":
    unittest.main()
