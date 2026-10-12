from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def configure_in_child(home, extra_environment=None):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MARA_", "KH_", "THEFLOW_", "KOTAEMON_"))
    }
    environment.update(MARA_APP_HOME=str(home), **(extra_environment or {}))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, os; from pathlib import Path; "
            "from sidecar.desktop_data_root import configure_desktop_data_root; "
            "root = configure_desktop_data_root(Path(os.environ['MARA_APP_HOME']) / 'desktop'); "
            "print(json.dumps({'root': str(root), 'office': os.getenv('KH_OFFICE_TO_PDF_INDEXING')}))",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class SharedDesktopProfileTest(unittest.TestCase):
    def test_loads_the_same_data_directory_as_web_and_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve() / "shared"
            config = home / "config"
            config.mkdir(parents=True)
            app_data = home / "existing-data"
            (config / ".env").write_text(
                f"KH_APP_DATA_DIR={app_data.as_posix()}\n"
                "KH_OFFICE_TO_PDF_INDEXING=true\n",
                encoding="utf-8",
            )
            actual = configure_in_child(home)
            self.assertEqual(Path(actual["root"]), app_data)
            self.assertEqual(actual["office"], "true")
            self.assertFalse((home / "desktop/state/ktem_app_data").exists())

    def test_shared_profile_keeps_explicit_data_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve() / "shared"
            config = home / "config"
            config.mkdir(parents=True)
            (config / ".env").write_text(
                f"KH_APP_DATA_DIR={(home / 'configured').as_posix()}\n",
                encoding="utf-8",
            )
            explicit = home / "explicit"
            actual = configure_in_child(home, {"KH_APP_DATA_DIR": str(explicit)})
            self.assertEqual(Path(actual["root"]), explicit)

    def test_shared_profile_defaults_to_the_common_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve() / "shared"
            actual = configure_in_child(home)
            self.assertEqual(Path(actual["root"]), home / "data")
