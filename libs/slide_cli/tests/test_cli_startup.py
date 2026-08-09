import json
import os
import subprocess
import sys
import types
from pathlib import Path


def test_importing_cli_module_does_not_eagerly_import_heavy_modules():
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_paths = [
        str(repo_root / "libs" / "slide_cli"),
        str(repo_root / "libs" / "ktem"),
        str(repo_root / "libs" / "kotaemon"),
    ]
    if existing_pythonpath:
        source_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(source_paths)

    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "import slide_cli.cli; "
            "targets = ["
            "'slide_cli.docqa_cli', "
            "'slide_cli.runtime', "
            "'ktem.docqa', "
            "'ktem.auth.service', "
            "'ktem.db.models', "
            "'kotaemon.agents'"
            "]; "
            "print(json.dumps({name: (name in sys.modules) for name in targets}))"
        ),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip())
    assert payload == {
        "slide_cli.docqa_cli": False,
        "slide_cli.runtime": False,
        "ktem.docqa": False,
        "ktem.auth.service": False,
        "ktem.db.models": False,
        "kotaemon.agents": False,
    }


def test_collecting_docqa_doctor_payload_avoids_heavy_docqa_imports():
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_paths = [
        str(repo_root / "libs" / "slide_cli"),
        str(repo_root / "libs" / "ktem"),
        str(repo_root / "libs" / "kotaemon"),
    ]
    if existing_pythonpath:
        source_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(source_paths)

    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "from slide_cli.docqa_runtime import collect_docqa_doctor_payload; "
            "payload = collect_docqa_doctor_payload(); "
            "targets = ["
            "'ktem.docqa', "
            "'pypdf', "
            "'kotaemon.indices'"
            "]; "
            "print(json.dumps({"
            "'targets': {name: (name in sys.modules) for name in targets}, "
            "'has_keys': sorted(payload.keys())"
            "}))"
        ),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip())
    assert payload["targets"] == {
        "ktem.docqa": False,
        "pypdf": False,
        "kotaemon.indices": False,
    }
    for key in [
        "ok",
        "app_name",
        "default_user_id",
        "index_name",
        "llm_default",
        "embedding_default",
        "file_count",
        "session_count",
        "graph_cache_dir",
        "issues",
        "warnings",
    ]:
        assert key in payload["has_keys"]


def test_building_docqa_request_does_not_import_ktem_docqa():
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_paths = [
        str(repo_root / "libs" / "slide_cli"),
        str(repo_root / "libs" / "ktem"),
        str(repo_root / "libs" / "kotaemon"),
    ]
    if existing_pythonpath:
        source_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(source_paths)

    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "from slide_cli.docqa_cli import _create_docqa_request; "
            "_create_docqa_request(prompt='hello'); "
            "targets = ["
            "'ktem.docqa', "
            "'pypdf', "
            "'kotaemon.indices'"
            "]; "
            "print(json.dumps({name: (name in sys.modules) for name in targets}))"
        ),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip())
    assert payload == {
        "ktem.docqa": False,
        "pypdf": False,
        "kotaemon.indices": False,
    }


def test_create_docqa_runtime_bootstraps_before_import(monkeypatch):
    import slide_cli.docqa_runtime as module

    events: list[str] = []

    monkeypatch.setattr(module, "ensure_llama_index_nltk_cache", lambda: None)

    fake_bootstrap_module = types.ModuleType("ktem.runtime_bootstrap")

    def _bootstrap():
        events.append("bootstrap")

    setattr(fake_bootstrap_module, "bootstrap_runtime_settings", _bootstrap)

    fake_docqa_module = types.ModuleType("ktem.docqa")

    class _FakeRuntime:
        def __init__(self):
            events.append("runtime")

    setattr(fake_docqa_module, "DocQARuntime", _FakeRuntime)

    monkeypatch.setitem(sys.modules, "ktem.runtime_bootstrap", fake_bootstrap_module)
    monkeypatch.setitem(sys.modules, "ktem.docqa", fake_docqa_module)

    runtime = module.create_docqa_runtime()

    assert type(runtime).__name__ == "_FakeRuntime"
    assert events == ["bootstrap", "runtime"]


def test_create_docqa_runtime_can_limit_desktop_only_features(monkeypatch):
    import slide_cli.docqa_runtime as module

    events: list[str] = []
    monkeypatch.setattr(module, "ensure_llama_index_nltk_cache", lambda: None)

    fake_bootstrap_module = types.ModuleType("ktem.runtime_bootstrap")

    def _bootstrap():
        events.append("bootstrap")

    setattr(fake_bootstrap_module, "bootstrap_runtime_settings", _bootstrap)

    fake_settings = types.SimpleNamespace(
        KH_REASONINGS=["reasoning.module"],
        KH_WEB_SEARCH_BACKEND="web_search.module",
        KH_FILE_INDEX_ARTIFACTS_ENABLED=True,
    )
    fake_settings_module = types.ModuleType("theflow.settings")
    setattr(fake_settings_module, "settings", fake_settings)

    fake_docqa_module = types.ModuleType("ktem.docqa")

    class _FakeRuntime:
        def __init__(self):
            events.append("runtime")

    setattr(fake_docqa_module, "DocQARuntime", _FakeRuntime)

    monkeypatch.setitem(sys.modules, "ktem.runtime_bootstrap", fake_bootstrap_module)
    monkeypatch.setitem(sys.modules, "theflow.settings", fake_settings_module)
    monkeypatch.setitem(sys.modules, "ktem.docqa", fake_docqa_module)

    runtime = module.create_docqa_runtime(
        include_query_features=False,
        include_file_artifacts=False,
    )

    assert type(runtime).__name__ == "_FakeRuntime"
    assert fake_settings.KH_REASONINGS == []
    assert fake_settings.KH_WEB_SEARCH_BACKEND == ""
    assert fake_settings.KH_FILE_INDEX_ARTIFACTS_ENABLED is False
    assert events == ["bootstrap", "runtime"]


def test_create_docqa_runtime_can_select_a_narrow_reasoning_profile(monkeypatch):
    import slide_cli.docqa_runtime as module

    monkeypatch.setattr(module, "ensure_llama_index_nltk_cache", lambda: None)
    monkeypatch.setattr(module, "ensure_tiktoken_cache", lambda: None)

    fake_bootstrap_module = types.ModuleType("ktem.runtime_bootstrap")
    setattr(fake_bootstrap_module, "bootstrap_runtime_settings", lambda: None)
    fake_settings = types.SimpleNamespace(
        KH_REASONINGS=["reasoning.default"],
        KH_WEB_SEARCH_BACKEND="web_search.module",
        KH_FILE_INDEX_ARTIFACTS_ENABLED=True,
    )
    fake_settings_module = types.ModuleType("theflow.settings")
    setattr(fake_settings_module, "settings", fake_settings)
    fake_docqa_module = types.ModuleType("ktem.docqa")
    setattr(fake_docqa_module, "DocQARuntime", lambda: object())

    monkeypatch.setitem(sys.modules, "ktem.runtime_bootstrap", fake_bootstrap_module)
    monkeypatch.setitem(sys.modules, "theflow.settings", fake_settings_module)
    monkeypatch.setitem(sys.modules, "ktem.docqa", fake_docqa_module)

    module.create_docqa_runtime(
        include_query_features=True,
        include_file_artifacts=False,
        reasoning_paths=("ktem.reasoning.mara.MaraAgentPipeline",),
    )

    assert fake_settings.KH_REASONINGS == ["ktem.reasoning.mara.MaraAgentPipeline"]
    assert fake_settings.KH_WEB_SEARCH_BACKEND == "web_search.module"
    assert fake_settings.KH_FILE_INDEX_ARTIFACTS_ENABLED is False


def test_ensure_llama_index_nltk_cache_sets_bundled_cache_without_heavy_imports(
    monkeypatch, tmp_path
):
    import slide_cli.docqa_runtime as module

    cache_dir = tmp_path / "llama_index" / "core" / "_static" / "nltk_cache"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr(module.sys, "path", [str(tmp_path)])
    monkeypatch.delenv("NLTK_DATA", raising=False)
    monkeypatch.delitem(sys.modules, "llama_index.core", raising=False)
    monkeypatch.delitem(sys.modules, "nltk", raising=False)

    module.ensure_llama_index_nltk_cache()

    assert os.environ["NLTK_DATA"] == str(cache_dir)
    assert "llama_index.core" not in sys.modules
    assert "nltk" not in sys.modules


def test_ensure_tiktoken_cache_sets_bundled_cache_without_importing_tiktoken(
    monkeypatch, tmp_path
):
    import slide_cli.docqa_runtime as module

    cache_dir = tmp_path / "tiktoken_cache"
    cache_dir.mkdir()

    monkeypatch.setattr(module.sys, "path", [str(tmp_path)])
    monkeypatch.delenv("TIKTOKEN_CACHE_DIR", raising=False)
    monkeypatch.delitem(sys.modules, "tiktoken", raising=False)

    module.ensure_tiktoken_cache()

    assert os.environ["TIKTOKEN_CACHE_DIR"] == str(cache_dir)
    assert "tiktoken" not in sys.modules


def test_importing_docqa_cli_does_not_emit_nltk_download_chatter():
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_paths = [
        str(repo_root / "libs" / "slide_cli"),
        str(repo_root / "libs" / "ktem"),
        str(repo_root / "libs" / "kotaemon"),
    ]
    if existing_pythonpath:
        source_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(source_paths)

    command = [
        sys.executable,
        "-c",
        "import slide_cli.docqa_cli; print('ok')",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[nltk_data]" not in completed.stderr
    assert "punkt_tab" not in completed.stderr.lower()
    assert completed.stdout.strip().endswith("ok")
