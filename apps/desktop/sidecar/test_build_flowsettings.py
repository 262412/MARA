from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BuildFlowsettingsTests(unittest.TestCase):
    def test_routes_build_time_theflow_state_to_the_isolated_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir).resolve()
            with patch.dict(
                os.environ,
                {"MARA_DESKTOP_BUILD_RUNTIME_ROOT": str(runtime_root)},
                clear=False,
            ):
                sys.modules.pop("sidecar.build_flowsettings", None)
                settings = importlib.import_module("sidecar.build_flowsettings")

            self.assertEqual(
                Path(settings.STORAGE["prefix"]),
                runtime_root / "cache" / "theflow",
            )
            self.assertEqual(
                Path(settings.CACHE["path"]),
                runtime_root / "cache" / "components",
            )


if __name__ == "__main__":
    unittest.main()
