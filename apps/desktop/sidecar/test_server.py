from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from typing import cast

from .server import PROTOCOL_VERSION, build_server


class SidecarContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.server = build_server(self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        raw_host, port = self.server.server_address
        host = cast(str, raw_host)
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path: str, token: str | None = None) -> tuple[int, dict]:
        request = urllib.request.Request(f"{self.base_url}{path}")
        if token is not None:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_health_rejects_missing_credentials(self) -> None:
        status, payload = self.request("/health")

        self.assertEqual(status, 401)
        self.assertEqual(payload["code"], "unauthorized")

    def test_health_reports_only_runtime_metadata(self) -> None:
        status, payload = self.request("/health", self.token)

        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "healthy")
        self.assertEqual(payload["protocol"], PROTOCOL_VERSION)
        self.assertNotIn("token", payload)
        self.assertNotIn("port", payload)

    def test_capabilities_are_explicit(self) -> None:
        status, payload = self.request("/capabilities", self.token)

        self.assertEqual(status, 200)
        self.assertEqual(payload["capabilities"], ["health", "lifecycle"])


if __name__ == "__main__":
    unittest.main()
