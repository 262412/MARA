from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pytest_runtime_isolation import OWNER_MARKER, ActiveTestRuntime
from pytest_runtime_isolation import TestRuntimePaths as RuntimePaths


@pytest.fixture
def owned_runtime(monkeypatch, tmp_path):
    import pytest_runtime_plugin as plugin

    root = tmp_path / "owned-session"
    root.mkdir()
    token = "basetemp-boundary-test"
    (root / OWNER_MARKER).write_text(token, encoding="utf-8")
    for subtree in ("config", "cache", "ktem_app_data", "outputs", "tmp"):
        directory = root / subtree
        directory.mkdir()
        (directory / "keep").write_text(subtree, encoding="utf-8")
    runtime = ActiveTestRuntime(
        environment={},
        snapshot={},
        paths=RuntimePaths.from_root(root),
        owned_root=root,
        owner_token=token,
    )
    monkeypatch.setattr(plugin, "_TEST_RUNTIME", runtime)
    return plugin, runtime


def _state(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _pytest_clears_basetemp(config):
    factory = pytest.TempPathFactory(
        given_basetemp=Path(config.option.basetemp),
        retention_count=3,
        retention_policy="all",
        trace=lambda *_args: None,
        _ispytest=True,
    )
    return factory.getbasetemp()


@pytest.mark.parametrize(
    "relative",
    [
        ".",
        "config",
        "config/child",
        "cache",
        "cache/child",
        "ktem_app_data",
        "outputs",
        "tmp",
    ],
)
def test_basetemp_cannot_clear_owner_or_runtime_state(owned_runtime, relative):
    plugin, runtime = owned_runtime
    root = runtime.paths.root
    before = _state(root)
    config = SimpleNamespace(option=SimpleNamespace(basetemp=str(root / relative)))

    with pytest.raises(pytest.UsageError, match="basetemp"):
        plugin.pytest_configure(config)
        _pytest_clears_basetemp(config)

    assert _state(root) == before


def test_external_basetemp_is_rejected_before_clear(owned_runtime):
    plugin, runtime = owned_runtime
    root = runtime.paths.root
    before = _state(root)
    config = SimpleNamespace(
        option=SimpleNamespace(basetemp=str(root.parent / "outside"))
    )
    with pytest.raises(pytest.UsageError, match="basetemp"):
        plugin.pytest_configure(config)
        _pytest_clears_basetemp(config)
    assert _state(root) == before


@pytest.mark.parametrize("relative", [None, "pytest", "case-files", "pytest/nested"])
def test_dedicated_basetemp_preserves_owner_and_state(owned_runtime, relative):
    plugin, runtime = owned_runtime
    root = runtime.paths.root
    before = _state(root)
    base = str(root / relative) if relative is not None else None
    config = SimpleNamespace(option=SimpleNamespace(basetemp=base))

    plugin.pytest_configure(config)

    selected = Path(config.option.basetemp)
    assert selected == root / (relative or "pytest")
    selected.mkdir(parents=True)
    stale = selected / "stale.txt"
    stale.write_text("pytest should clear this", encoding="utf-8")
    assert _pytest_clears_basetemp(config) == selected
    assert not stale.exists()
    (selected / "case.txt").write_text("case", encoding="utf-8")
    assert all(_state(root)[name] == value for name, value in before.items())


@pytest.mark.parametrize("target", [".", "cache", "pytest"])
def test_basetemp_symlink_alias_is_rejected(owned_runtime, target):
    plugin, runtime = owned_runtime
    root = runtime.paths.root
    destination = root / target
    destination.mkdir(exist_ok=True)
    alias = root / "alias"
    try:
        alias.symlink_to(destination, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and error.winerror == 1314:
            pytest.skip(
                "Windows token cannot create symlinks; native case runs in Ubuntu CI"
            )
        raise
    before = _state(root)
    config = SimpleNamespace(option=SimpleNamespace(basetemp=str(alias)))
    with pytest.raises(pytest.UsageError, match="basetemp"):
        plugin.pytest_configure(config)
        _pytest_clears_basetemp(config)
    assert _state(root) == before


def test_basetemp_requires_intact_ownership_marker(owned_runtime):
    plugin, runtime = owned_runtime
    marker = runtime.paths.root / OWNER_MARKER
    marker.write_text("changed-owner", encoding="utf-8")
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None))
    with pytest.raises(RuntimeError, match="not owned"):
        plugin.pytest_configure(config)
    assert marker.read_text(encoding="utf-8") == "changed-owner"
