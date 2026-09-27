from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native-resource-receipt.py"
owned_role = runpy.run_path(str(SCRIPT))["owned_role"]


class NativeResourceReceiptTests(unittest.TestCase):
    def test_package_identity_requires_a_real_directory_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            repository = Path(root).resolve()
            package = repository / "package"
            self.assertEqual(
                owned_role({"exe": str(package / "sidecar")}, package, repository),
                "packaged_application",
            )
            self.assertIsNone(
                owned_role(
                    {"exe": str(repository / "package-other/sidecar")},
                    package,
                    repository,
                )
            )

    def test_fixture_identity_keeps_the_venv_path_and_never_prints_arguments(self):
        with tempfile.TemporaryDirectory() as root:
            repository = Path(root).resolve()
            package = repository / "package"
            info = {
                "exe": str(repository.parent / "system-python"),
                "cwd": str(repository / "apps/desktop"),
                "cmdline": [
                    "../../.venv/bin/python",
                    "-m",
                    "sidecar.smoke_embedding_server",
                    "--token",
                    "owned-fake-secret",
                ],
            }
            self.assertEqual(
                owned_role(info, package, repository), "smoke_model_fixture"
            )
            info["cwd"] = str(repository.parent / "other-checkout")
            self.assertIsNone(owned_role(info, package, repository))
