from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from .server_runtime import apply_smoke_startup_delay, create_loopback_listener


class ServerRuntimeTest(unittest.TestCase):
    def test_smoke_delay_is_bounded_and_invalid_values_fail_closed(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS": "9000"},
            ),
            patch("sidecar.server_runtime.time.sleep") as sleep,
        ):
            self.assertTrue(apply_smoke_startup_delay())
            sleep.assert_called_once_with(5.0)

        with patch.dict(
            os.environ,
            {"MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS": "invalid"},
        ):
            self.assertFalse(apply_smoke_startup_delay())

    def test_listener_uses_an_ephemeral_loopback_port(self) -> None:
        listener = create_loopback_listener()
        try:
            host, port = listener.getsockname()
            self.assertEqual(host, "127.0.0.1")
            self.assertGreater(port, 0)
        finally:
            listener.close()


if __name__ == "__main__":
    unittest.main()
