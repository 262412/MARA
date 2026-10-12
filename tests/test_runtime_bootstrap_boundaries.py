from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def bootstrap(monkeypatch):
    name = "_bootstrap_boundary_probe"
    path = Path(__file__).resolve().parents[1] / "libs/ktem/ktem/runtime_bootstrap.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("search", ["single", "multiple", "empty-elements", "empty"])
def test_normal_nltk_search_paths_do_not_require_writable_resources(
    bootstrap, monkeypatch, tmp_path, search
):
    first = tmp_path / "readonly-resources"
    second = tmp_path / "optional-resources"
    punkt = first / "tokenizers/punkt"
    punkt.mkdir(parents=True)
    sentinel = punkt / "resource.txt"
    sentinel.write_text("read-only resource", encoding="utf-8")
    searches = {
        "single": str(first),
        "multiple": os.pathsep.join((str(first), str(second))),
        "empty-elements": os.pathsep.join(("", str(first), "", str(second), "")),
        "empty": "",
    }
    raw = searches[search]
    monkeypatch.setattr(os, "environ", {"NLTK_DATA": raw})
    monkeypatch.setattr(bootstrap.sys, "path", [])

    def readonly(*_args, **_kwargs):
        raise PermissionError("resource search directories are read-only")

    monkeypatch.setattr(Path, "mkdir", readonly)
    bootstrap.ensure_llama_index_nltk_cache()

    assert os.environ["NLTK_DATA"] == raw
    assert sentinel.read_text(encoding="utf-8") == "read-only resource"
    assert not second.exists()


def test_normal_bundled_nltk_resources_are_not_modified(
    bootstrap, monkeypatch, tmp_path
):
    cache = tmp_path / "llama_index/core/_static/nltk_cache"
    cache.mkdir(parents=True)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setattr(bootstrap.sys, "path", [str(tmp_path)])

    def readonly(*_args, **_kwargs):
        raise PermissionError("installed resources are read-only")

    monkeypatch.setattr(Path, "mkdir", readonly)
    bootstrap.ensure_llama_index_nltk_cache()

    assert os.environ["NLTK_DATA"] == str(cache)
    assert list(cache.iterdir()) == []


def test_owned_nltk_list_prepares_only_first_search_directory(
    bootstrap, monkeypatch, tmp_path
):
    root = tmp_path / "session"
    root.mkdir()
    first, second = root / "nltk-first", root / "nltk-second"
    raw = os.pathsep.join(("", str(first), "", str(second), ""))
    monkeypatch.setattr(
        os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root), "NLTK_DATA": raw}
    )

    bootstrap.ensure_llama_index_nltk_cache()

    assert (first / "tokenizers/punkt").is_dir()
    assert not second.exists()
    assert os.environ["NLTK_DATA"] == raw


@pytest.mark.parametrize("raw", ["", os.pathsep])
def test_owned_empty_nltk_list_uses_session_cache(
    bootstrap, monkeypatch, tmp_path, raw
):
    root = tmp_path / "session"
    root.mkdir()
    monkeypatch.setattr(
        os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root), "NLTK_DATA": raw}
    )

    bootstrap.ensure_llama_index_nltk_cache()

    assert os.environ["NLTK_DATA"] == str(root / "cache/nltk")
    assert (root / "cache/nltk/tokenizers/punkt").is_dir()


@pytest.mark.parametrize("entrypoint", ["validate", "prepare"])
def test_nltk_list_rejects_external_later_entry_before_any_write(
    bootstrap, monkeypatch, tmp_path, entrypoint
):
    root = tmp_path / "session"
    root.mkdir()
    raw = os.pathsep.join((str(root / "nltk"), str(tmp_path / "fake-user")))
    monkeypatch.setattr(
        os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root), "NLTK_DATA": raw}
    )

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("NLTK prepared a directory before validating every search entry")

    monkeypatch.setattr(Path, "mkdir", unexpected_write)
    with pytest.raises(RuntimeError, match="outside.*test runtime"):
        if entrypoint == "validate":
            bootstrap.validate_test_runtime_paths(os.environ)
        else:
            bootstrap.ensure_llama_index_nltk_cache()
    assert not (tmp_path / "fake-user").exists()


def _symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip(
                "Windows token cannot create symlinks; native case runs in Ubuntu CI"
            )
        raise


def test_owned_named_settings_module_is_accepted(bootstrap, monkeypatch, tmp_path):
    root = tmp_path / "session"
    root.mkdir()
    (root / "mara_benchmark_flowsettings.py").write_text(
        f"KH_DATABASE = 'sqlite:///:memory:'\nSTORAGE = {{'prefix': {str(root / 'storage')!r}}}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root)})
    monkeypatch.syspath_prepend(str(root))

    values = bootstrap._load_settings_values("mara_benchmark_flowsettings")

    assert values["KH_DATABASE"] == "sqlite:///:memory:"
    assert values["STORAGE"]["prefix"] == str(root / "storage")
    monkeypatch.delitem(sys.modules, "mara_benchmark_flowsettings")


@pytest.mark.parametrize("kind", ["module", "package", "symlink"])
def test_external_named_settings_is_rejected_before_execution(
    bootstrap, monkeypatch, tmp_path, kind
):
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "fake-user"
    outside.mkdir()
    if kind == "package":
        package = outside / "external_settings"
        package.mkdir()
        source = package / "__init__.py"
        selected = "external_settings.config"
    else:
        source = outside / "external_settings.py"
        selected = "external_settings"
    source.write_text(
        "raise AssertionError('external config executed')\n", encoding="utf-8"
    )
    if kind == "symlink":
        _symlink(root / "external_settings.py", source)
        search_root = root
    else:
        search_root = outside
    monkeypatch.setattr(os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root)})
    monkeypatch.syspath_prepend(str(search_root))

    with pytest.raises(RuntimeError, match="outside.*test runtime"):
        bootstrap._load_settings_values(selected)
    assert "external_settings" not in sys.modules


@pytest.mark.parametrize("entrypoint", ["finder", "loader", "explicit"])
@pytest.mark.parametrize("kind", ["leaf", "parent"])
def test_external_settings_symlink_is_rejected_before_execution(
    bootstrap, monkeypatch, tmp_path, entrypoint, kind
):
    root = tmp_path / "session"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    outside = tmp_path / "fake-user"
    outside.mkdir()
    source = outside / "flowsettings.py"
    source.write_text(
        "raise AssertionError('external configuration executed')\n", encoding="utf-8"
    )
    if kind == "leaf":
        selected = workspace / "flowsettings.py"
        _symlink(selected, source)
    else:
        alias = root / "alias"
        _symlink(alias, outside, directory=True)
        selected = alias / "flowsettings.py"
    monkeypatch.setattr(os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root)})
    monkeypatch.setattr(bootstrap.sys, "path", [str(selected.parent)])
    monkeypatch.chdir(workspace)

    with pytest.raises(RuntimeError, match="outside.*test runtime"):
        if entrypoint == "finder":
            # Parent aliases are not eligible directories; an explicit entry
            # is used below to cover their refusal before configuration I/O.
            if kind == "parent":
                assert bootstrap.find_local_flowsettings() is None
                bootstrap._load_settings_module_from_path(selected)
            else:
                bootstrap.find_local_flowsettings()
        elif entrypoint == "loader":
            bootstrap._load_settings_module_from_path(selected)
        else:
            monkeypatch.setenv("THEFLOW_SETTINGS_MODULE", str(selected))
            bootstrap._load_settings_values(str(selected))


@pytest.mark.parametrize("initialized", [False, True])
@pytest.mark.parametrize("setting", ["STORAGE", "KH_DATABASE"])
def test_owned_settings_values_are_validated_before_theflow_initialization(
    bootstrap, monkeypatch, tmp_path, initialized, setting
):
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "fake-user"
    value = (
        {"__type__": "theflow.storage.LocalStorage", "prefix": str(outside)}
        if setting == "STORAGE"
        else f"sqlite:///{outside / 'sql.db'}"
    )
    source = root / "flowsettings.py"
    source.write_text(f"{setting} = {value!r}\n", encoding="utf-8")
    monkeypatch.setattr(os, "environ", {"MARA_PYTEST_RUNTIME_ROOT": str(root)})
    settings = SimpleNamespace(_initialized=initialized, EXISTING="keep")
    original = vars(settings).copy()
    monkeypatch.setitem(
        sys.modules, "theflow.settings", SimpleNamespace(settings=settings)
    )

    with pytest.raises(RuntimeError, match="outside.*test runtime"):
        bootstrap._synchronize_theflow_settings(str(source))

    assert vars(settings) == original
    assert not outside.exists()


@pytest.mark.parametrize("test_mode", [False, True])
def test_owned_workspace_discovery_and_loading_preserve_selection(
    bootstrap, monkeypatch, tmp_path, test_mode
):
    root = tmp_path / "session"
    root.mkdir()
    source = root / "flowsettings.py"
    source.write_text("KH_APP_NAME = 'owned workspace'\n", encoding="utf-8")
    environment = {"MARA_PYTEST_RUNTIME_ROOT": str(root)} if test_mode else {}
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.chdir(root)
    monkeypatch.setattr(bootstrap.sys, "path", [])

    assert bootstrap.find_local_flowsettings() == source
    assert bootstrap._load_settings_values(str(source)) == {
        "KH_APP_NAME": "owned workspace"
    }
