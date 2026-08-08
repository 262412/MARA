from __future__ import annotations

import json
import threading
import unittest
from urllib.request import Request, urlopen

from .smoke_embedding_server import create_server


class SmokeEmbeddingServerTest(unittest.TestCase):
    def test_serves_deterministic_openai_compatible_embeddings(self) -> None:
        server = create_server("smoke-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/embeddings",
                data=json.dumps(
                    {"input": ["paper", [1, 2, 3]], "model": "smoke-embedding"}
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer smoke-token",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                payload = json.load(response)

            self.assertEqual(response.status, 200)
            self.assertEqual([item["index"] for item in payload["data"]], [0, 1])
            self.assertEqual(len(payload["data"][0]["embedding"]), 16)
            self.assertEqual(
                payload["data"][0]["embedding"],
                payload["data"][0]["embedding"],
            )
            self.assertNotEqual(
                payload["data"][0]["embedding"],
                payload["data"][1]["embedding"],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
