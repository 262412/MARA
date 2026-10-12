"""Pre-spawn isolation, including final argv/env mutation counterexamples."""

import hashlib
import io
import os
import subprocess
from pathlib import Path

import pytest

from scripts import install_owned_wheels as installer


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    owner = tmp_path / "owned"
    python = owner / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_bytes(b"owned interpreter fixture")
    (owner / "env/pyvenv.cfg").write_text("owned fixture")
    env = {
        "UV_PROJECT_ENVIRONMENT": str(owner / "env"),
        "UV_CACHE_DIR": str(owner / "uv-cache"),
        "PIP_CACHE_DIR": str(owner / "pip-cache"),
        "XDG_CACHE_HOME": str(owner / "cache"),
        "TEMP": str(owner / "tmp"),
        "TMP": str(owner / "tmp"),
        "TMPDIR": str(owner / "tmp"),
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_LINK_MODE": "copy",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    for name in ("uv-cache", "pip-cache", "cache", "tmp"):
        (owner / name).mkdir()
    wheels = {}
    for name in ("kotaemon", "ktem", "mara_app", "mara_research_cli"):
        path = tmp_path / f"{name}-0.0.40-py3-none-any.whl"
        path.write_bytes(name.encode())
        wheels[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    uv = tmp_path / "uv"
    uv.write_bytes(b"uv fixture")
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", spawn)
    return dict(uv=uv, owner=owner, env=env, wheels=wheels, log=io.StringIO()), calls


def test_exact_validated_snapshot_is_used_for_the_only_spawn(prepared, monkeypatch):
    kwargs, calls = prepared
    validate = installer._validate_launch
    checked = []

    def capture(command, env, owner, wheels):
        validate(command, env, owner, wheels)
        checked.append((command, env))
        # Changes in the caller cannot leak in after validation.
        kwargs["env"]["UV_CACHE_DIR"] = ""
        kwargs["wheels"].clear()

    monkeypatch.setattr(installer, "_validate_launch", capture)
    assert installer.install_wheels(**kwargs).returncode == 0
    assert len(calls) == 1
    command, options = calls[0]
    assert command is checked[0][0] and options["env"] is checked[0][1]
    assert command[1:4] == ["--no-config", "--offline", "--cache-dir"]
    assert command[command.index("--cache-dir") + 1] == options["env"]["UV_CACHE_DIR"]
    assert command[command.index("--python") + 1].startswith(
        str(kwargs["owner"] / "env")
    )
    assert options["cwd"] == kwargs["owner"]
    assert options["timeout"] == 180 and options["check"]
    assert "--no-cache" not in command and len(command[-4:]) == 4


@pytest.mark.parametrize(
    "key",
    [
        "UV_CACHE_DIR",
        "UV_PROJECT_ENVIRONMENT",
        "PIP_CACHE_DIR",
        "XDG_CACHE_HOME",
        "TEMP",
        "TMP",
        "TMPDIR",
    ],
)
@pytest.mark.parametrize("value", ["", "relative", "outside"])
def test_wrong_or_empty_root_is_rejected_before_spawn(prepared, tmp_path, key, value):
    kwargs, calls = prepared
    kwargs["env"][key] = str(tmp_path / "unowned") if value == "outside" else value
    with pytest.raises(ValueError):
        installer.install_wheels(**kwargs)
    assert calls == []
    assert not (tmp_path / "unowned").exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("UV_NO_CACHE", "1"),
        ("UV_CONFIG_FILE", "unowned"),
        ("UV_PYTHON", "unowned"),
        ("UV_PYTHON_INSTALL_DIR", "unowned"),
        ("UV_PYTHON_DOWNLOADS", "automatic"),
        ("UV_LINK_MODE", "hardlink"),
        ("PYTHONPATH", "unowned"),
        ("PYTHONHOME", "unowned"),
        ("PYTHONSTARTUP", "unowned"),
        ("PYTHONPYCACHEPREFIX", "unowned"),
        ("VIRTUAL_ENV", "unowned"),
        ("PIP_CONFIG_FILE", "unowned"),
        ("uv_cache_dir", "unowned"),
    ],
)
def test_inherited_override_is_not_silently_accepted(prepared, key, value):
    kwargs, calls = prepared
    kwargs["env"][key] = value
    with pytest.raises(ValueError):
        installer.install_wheels(**kwargs)
    assert calls == []


@pytest.mark.parametrize("mutation", ["python", "cache", "no-cache", "target"])
def test_final_argv_drift_is_rejected_at_spawn_boundary(
    prepared, monkeypatch, mutation
):
    kwargs, calls = prepared
    validate = installer._validate_launch

    def tamper(command, env, owner, wheels):
        if mutation in ("python", "cache"):
            flag = "--python" if mutation == "python" else "--cache-dir"
            command[command.index(flag) + 1] = str(owner.parent / "unowned")
        else:
            command.extend(
                ["--no-cache"] if mutation == "no-cache" else ["--target", "unowned"]
            )
        validate(command, env, owner, wheels)

    monkeypatch.setattr(installer, "_validate_launch", tamper)
    with pytest.raises(ValueError, match="Final installer arguments"):
        installer.install_wheels(**kwargs)
    assert calls == []


@pytest.mark.parametrize(
    "mutation", ["bytes", "missing", "distribution", "python", "venv", "owner"]
)
def test_untrusted_wheel_or_interpreter_input_never_spawns(prepared, mutation):
    kwargs, calls = prepared
    path = next(iter(kwargs["wheels"]))
    if mutation == "bytes":
        path.write_bytes(b"changed after manifest")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "distribution":
        kwargs["wheels"].pop(path)
    elif mutation == "python":
        suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        (kwargs["owner"] / "env" / suffix).unlink()
    elif mutation == "venv":
        (kwargs["owner"] / "env/pyvenv.cfg").unlink()
    else:
        kwargs["owner"] = Path("relative")
    with pytest.raises(ValueError):
        installer.install_wheels(**kwargs)
    assert calls == []


def test_child_failure_is_propagated_once(prepared, monkeypatch):
    kwargs, calls = prepared

    def fail(command, **options):
        calls.append(command)
        raise subprocess.CalledProcessError(9, command)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as failure:
        installer.install_wheels(**kwargs)
    assert failure.value.returncode == 9 and len(calls) == 1


@pytest.mark.parametrize(
    "key,value", [("UV_CACHE_DIR", ""), ("TMP", "outside"), ("PYTHONPATH", "outside")]
)
def test_final_environment_drift_is_rejected(prepared, monkeypatch, key, value):
    kwargs, calls = prepared
    validate = installer._validate_launch

    def tamper(command, env, owner, wheels):
        env[key] = value
        validate(command, env, owner, wheels)

    monkeypatch.setattr(installer, "_validate_launch", tamper)
    with pytest.raises(ValueError):
        installer.install_wheels(**kwargs)
    assert calls == []


@pytest.mark.parametrize("directory", ["tmp", "uv-cache"])
def test_missing_directory_cannot_trigger_default_temp_or_cache_fallback(
    prepared, directory
):
    kwargs, calls = prepared
    (kwargs["owner"] / directory).rmdir()
    with pytest.raises(ValueError, match="directory is missing"):
        installer.install_wheels(**kwargs)
    assert calls == []
