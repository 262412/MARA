from pathlib import Path

import tomli


def test_ktem_contracts_is_included_in_package_discovery():
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project = tomli.loads(project_file.read_text(encoding="utf-8"))

    includes = project["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "ktem_contracts*" in includes
