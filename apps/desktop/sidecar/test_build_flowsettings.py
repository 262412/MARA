from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BuildFlowsettingsTests(unittest.TestCase):
    def test_routes_build_time_theflow_state_to_the_isolated_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir).resolve()
            desktop_root = Path(__file__).resolve().parents[1]
            env = os.environ.copy()
            env["MARA_DESKTOP_BUILD_RUNTIME_ROOT"] = str(runtime_root)
            env["PYTHONPATH"] = os.pathsep.join(
                [str(desktop_root), env.get("PYTHONPATH", "")]
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json; "
                        "from sidecar import build_flowsettings as settings; "
                        "print(json.dumps({"
                        "'storage': settings.STORAGE['prefix'], "
                        "'cache': settings.CACHE['path']}))"
                    ),
                ],
                cwd=runtime_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            settings = json.loads(result.stdout)

            self.assertEqual(
                Path(settings["storage"]),
                runtime_root / "cache" / "theflow",
            )
            self.assertEqual(
                Path(settings["cache"]),
                runtime_root / "cache" / "components",
            )
            self.assertFalse((runtime_root / ".theflow").exists())


if __name__ == "__main__":
    unittest.main()
