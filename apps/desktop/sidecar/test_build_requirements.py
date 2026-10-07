from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from packaging.requirements import Requirement


class SidecarBuildRequirementsTest(unittest.TestCase):
    def test_build_install_preserves_locked_server_runtime(self) -> None:
        sidecar = Path(__file__).resolve().parent
        requirements = {}
        for line in (sidecar / "requirements-build.txt").read_text().splitlines():
            requirement = Requirement(line)
            requirements[requirement.name] = str(requirement.specifier)
        lock = tomllib.loads((sidecar.parents[2] / "uv.lock").read_text())
        locked = {
            package["name"]: package["version"]
            for package in lock["package"]
            if package["name"] in ("fastapi", "uvicorn")
        }

        for name in ("fastapi", "uvicorn"):
            with self.subTest(package=name):
                self.assertEqual(requirements[name], "==" + locked[name])
