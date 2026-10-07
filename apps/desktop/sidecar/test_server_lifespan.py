from __future__ import annotations

import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from .index_tasks import IndexTaskManager
from .query_tasks import QueryTaskManager
from .server import create_app
from .test_server import StubApplicationService


class SidecarLifespanTest(unittest.TestCase):
    def test_shutdown_closes_both_managers_after_serving_requests(self) -> None:
        index = Mock(spec=IndexTaskManager)
        query = Mock(spec=QueryTaskManager)
        app = create_app("test-token", StubApplicationService(), index, query)

        with TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 401)
            index.close.assert_not_called()
            query.close.assert_not_called()

        index.close.assert_called_once_with()
        query.close.assert_called_once_with()

    def test_shutdown_closes_managers_when_client_context_raises(self) -> None:
        index = Mock(spec=IndexTaskManager)
        query = Mock(spec=QueryTaskManager)
        app = create_app("test-token", StubApplicationService(), index, query)

        with self.assertRaisesRegex(RuntimeError, "client failed"):
            with TestClient(app):
                raise RuntimeError("client failed")

        index.close.assert_called_once_with()
        query.close.assert_called_once_with()
