from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import PlatformDirs

PACKAGE_FLOWSETTINGS_MODULE = "ktem.default_flowsettings"
BOOTSTRAP_MARKER_ENV = "KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED"
RUNTIME_SOURCE_ATTR = "_kotaemon_runtime_source"


def _test_runtime_root() -> Path | None:
    value = os.environ.get("MARA_PYTEST_RUNTIME_ROOT")
    if not value:
        return None
    root = Path(value).expanduser().absolute()
    if root != root.resolve():
        raise RuntimeError("Test runtime root must not traverse a symlink")
    return root


def validate_test_runtime_paths(values) -> None:
    """Fail before I/O when an activated test config escapes its session."""
    root = _test_runtime_root()
    if root is None:
        return
    extra_paths = {
        "MARA_RUNTIME_DIR",
        "MARA_OUTPUT_DIR",
        "MARA_DESKTOP_DATA_DIR",
        "GRADIO_TEMP_DIR",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HF_XET_CACHE",
        "TORCH_HOME",
        "TIKTOKEN_CACHE_DIR",
        "NLTK_DATA",
        "TMP",
        "TEMP",
        "TMPDIR",
    }
    for name, value in values.items():
        if value is None or value == "":
            continue
        if name == "KH_DATABASE":
            if value == "sqlite:///:memory:":
                continue
            if not str(value).startswith("sqlite:///"):
                raise RuntimeError("Database is outside the isolated test runtime")
            value = str(value).removeprefix("sqlite:///")
        elif name in {"STORAGE", "KH_DOCSTORE", "KH_VECTORSTORE"}:
            value = value.get("prefix" if name == "STORAGE" else "path")
            if value is None:
                continue
        elif name == "THEFLOW_SETTINGS_MODULE":
            if value == PACKAGE_FLOWSETTINGS_MODULE:
                continue
        elif not (
            name in extra_paths
            or (
                name.startswith(("KH_", "THEFLOW_"))
                and name.endswith(("_DIR", "_PATH"))
            )
            or (name.startswith("XDG_") and name.endswith("_HOME"))
        ):
            continue
        if not Path(value).expanduser().resolve().is_relative_to(root):
            raise RuntimeError(f"{name} is outside the isolated test runtime")


def _prepare_test_configuration() -> None:
    if _test_runtime_root() is None:
        return
    validate_test_runtime_paths(os.environ)
    from decouple import Config, RepositoryEmpty, config

    # The ordinary AutoConfig searches source parents for .env/settings.ini.
    # Test-owned .env files are loaded explicitly by load_packaged_runtime_env.
    config.config = Config(RepositoryEmpty())


@dataclass(frozen=True)
class RuntimePaths:
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    flowsettings_path: Path
    env_path: Path


def get_runtime_paths() -> RuntimePaths:
    validate_test_runtime_paths(os.environ)
    desktop_data_root = str(os.environ.get("MARA_DESKTOP_DATA_DIR", "") or "").strip()
    test_root = _test_runtime_root()
    if desktop_data_root:
        desktop_root = Path(desktop_data_root).expanduser().resolve()
        config_dir = desktop_root / "state" / "config"
        data_dir = desktop_root / "state" / "runtime"
        cache_dir = desktop_root / "cache"
    elif test_root is not None:
        config_dir = test_root / "config"
        data_dir = test_root / "ktem_app_data"
        cache_dir = test_root / "cache"
    else:
        dirs = PlatformDirs(appname="Kotaemon", appauthor="Cinnamon")
        config_dir = Path(dirs.user_config_dir).resolve()
        data_dir = Path(dirs.user_data_dir).resolve()
        cache_dir = Path(dirs.user_cache_dir).resolve()
    validate_test_runtime_paths(
        {
            "KH_CONFIG_DIR": config_dir,
            "KH_DATA_DIR": data_dir,
            "KH_CACHE_DIR": cache_dir,
            "KH_USER_ENV_PATH": config_dir / ".env",
            "KH_USER_FLOWSETTINGS_PATH": config_dir / "flowsettings.py",
        }
    )
    return RuntimePaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        flowsettings_path=config_dir / "flowsettings.py",
        env_path=config_dir / ".env",
    )


def find_local_flowsettings() -> Path | None:
    seen: set[Path] = set()
    candidates = [Path(os.getcwd()), *(Path(entry) for entry in sys.path if entry)]
    for candidate_dir in candidates:
        try:
            resolved_dir = candidate_dir.resolve()
        except Exception:
            continue
        if resolved_dir in seen:
            continue
        test_root = _test_runtime_root()
        if test_root is not None and not resolved_dir.is_relative_to(test_root):
            continue
        seen.add(resolved_dir)
        flowsettings_path = resolved_dir / "flowsettings.py"
        if flowsettings_path.is_file():
            return flowsettings_path
    return None


def _load_settings_module_from_path(settings_path: Path):
    spec = importlib.util.spec_from_file_location("flowsettings", settings_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load flowsettings from {settings_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_settings_values(settings_source: str) -> dict[str, object]:
    if settings_source == PACKAGE_FLOWSETTINGS_MODULE:
        load_packaged_runtime_env()

    settings_path = Path(settings_source)
    if settings_path.is_file():
        module = _load_settings_module_from_path(settings_path)
    else:
        module = importlib.import_module(settings_source)

    return {
        setting: getattr(module, setting)
        for setting in dir(module)
        if setting.isupper()
    }


def _synchronize_theflow_settings(settings_source: str) -> None:
    from theflow.settings import settings as flowsettings

    if not getattr(flowsettings, "_initialized", False):
        return

    if (
        getattr(flowsettings, RUNTIME_SOURCE_ATTR, None) == settings_source
        and "KH_FILESTORAGE_PATH" in flowsettings.__dict__
    ):
        return

    loaded_settings = _load_settings_values(settings_source)
    for setting in [name for name in flowsettings.__dict__ if name.isupper()]:
        del flowsettings.__dict__[setting]

    for setting, value in loaded_settings.items():
        setattr(flowsettings, setting, value)

    setattr(flowsettings, RUNTIME_SOURCE_ATTR, settings_source)
    flowsettings._initialized = True


def ensure_llama_index_nltk_cache() -> None:
    explicit_cache = os.environ.get("NLTK_DATA")
    if explicit_cache:
        punkt_dir = Path(explicit_cache) / "tokenizers" / "punkt"
        validate_test_runtime_paths({"NLTK_DATA": punkt_dir})
        punkt_dir.mkdir(parents=True, exist_ok=True)
        return
    for entry in sys.path:
        if not entry:
            continue
        cache_dir = (
            Path(entry).resolve() / "llama_index" / "core" / "_static" / "nltk_cache"
        )
        if not cache_dir.is_dir():
            continue
        validate_test_runtime_paths({"NLTK_DATA": cache_dir / "tokenizers" / "punkt"})
        (cache_dir / "tokenizers" / "punkt").mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("NLTK_DATA", str(cache_dir))
        return


def bootstrap_runtime_settings() -> str:
    _prepare_test_configuration()
    ensure_llama_index_nltk_cache()
    explicit_module = str(os.environ.get("THEFLOW_SETTINGS_MODULE", "") or "").strip()
    if explicit_module:
        _synchronize_theflow_settings(explicit_module)
        return explicit_module

    local_flowsettings = find_local_flowsettings()
    if local_flowsettings is not None:
        settings_source = str(local_flowsettings)
        _synchronize_theflow_settings(settings_source)
        return settings_source

    os.environ["THEFLOW_SETTINGS_MODULE"] = PACKAGE_FLOWSETTINGS_MODULE
    os.environ[BOOTSTRAP_MARKER_ENV] = "1"
    _synchronize_theflow_settings(PACKAGE_FLOWSETTINGS_MODULE)
    return PACKAGE_FLOWSETTINGS_MODULE


def bootstrap_packaged_runtime_settings() -> str:
    """Force the packaged user-XDG runtime regardless of workspace files."""
    os.environ["THEFLOW_SETTINGS_MODULE"] = PACKAGE_FLOWSETTINGS_MODULE
    os.environ[BOOTSTRAP_MARKER_ENV] = "1"
    _prepare_test_configuration()
    _synchronize_theflow_settings(PACKAGE_FLOWSETTINGS_MODULE)
    return PACKAGE_FLOWSETTINGS_MODULE


def load_packaged_runtime_env() -> Path:
    runtime_paths = get_runtime_paths()
    runtime_paths.config_dir.mkdir(parents=True, exist_ok=True)
    desktop_owned_config = bool(os.environ.get("MARA_DESKTOP_DATA_DIR"))
    desktop_model_environment = {
        name: value
        for name, value in os.environ.items()
        if name == "MARA_DESKTOP_MODEL_SETTINGS"
        or name == "MARA_DESKTOP_SETTINGS_REVISION"
        or name.startswith("MARA_DESKTOP_CHAT_")
        or name.startswith("MARA_DESKTOP_EMBEDDING_")
    }
    load_dotenv(runtime_paths.env_path, override=desktop_owned_config)
    validate_test_runtime_paths(os.environ)
    if desktop_model_environment.get("MARA_DESKTOP_MODEL_SETTINGS") == "1":
        for name in [
            key
            for key in os.environ
            if key == "MARA_DESKTOP_SETTINGS_REVISION"
            or key.startswith("MARA_DESKTOP_CHAT_")
            or key.startswith("MARA_DESKTOP_EMBEDDING_")
        ]:
            os.environ.pop(name, None)
        os.environ.update(desktop_model_environment)
    return runtime_paths.env_path


def describe_runtime_settings() -> dict[str, str]:
    runtime_paths = get_runtime_paths()
    explicit_module = str(os.environ.get("THEFLOW_SETTINGS_MODULE", "") or "").strip()
    local_flowsettings = find_local_flowsettings()
    bootstrapped = str(os.environ.get(BOOTSTRAP_MARKER_ENV, "") or "").strip() == "1"

    if explicit_module:
        if explicit_module == PACKAGE_FLOWSETTINGS_MODULE and bootstrapped:
            source = "package-default"
        else:
            source = "explicit-module"
        module = explicit_module
    elif local_flowsettings is not None:
        source = "workspace-flowsettings"
        module = str(local_flowsettings)
    else:
        source = "package-default"
        module = PACKAGE_FLOWSETTINGS_MODULE

    return {
        "settings_source": source,
        "settings_module": module,
        "workspace_flowsettings": str(local_flowsettings) if local_flowsettings else "",
        "config_dir": str(runtime_paths.config_dir),
        "data_dir": str(runtime_paths.data_dir),
        "cache_dir": str(runtime_paths.cache_dir),
        "user_flowsettings_path": str(runtime_paths.flowsettings_path),
        "user_env_path": str(runtime_paths.env_path),
    }


def build_user_flowsettings_template() -> str:
    return """# Kotaemon user override file
# Any UPPER_CASE setting defined here overrides the packaged defaults.
# Keep secrets in `.env` next to this file instead of committing them here.
#
# Examples:
# KH_APP_NAME = "My Kotaemon"
# KH_FEATURE_USER_MANAGEMENT = False
# KH_ENABLE_FIRST_SETUP = False
"""


def _build_user_env_template(
    *,
    auth_mode: str,
    include_password_file_setting: bool,
) -> str:
    password_file_setting = (
        "MARA_ADMIN_PASSWORD_FILE=\n" if include_password_file_setting else ""
    )
    return f"""# Kotaemon runtime environment example
# Copy the keys you need into `.env` in this same directory.

MARA_AUTH_MODE={auth_mode}
{password_file_setting}
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=<YOUR_OPENAI_KEY>
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-large

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=

COHERE_API_KEY=
MISTRAL_API_KEY=
VOYAGE_API_KEY=

LOCAL_MODEL=
LOCAL_MODEL_EMBEDDINGS=
"""


def build_user_env(*, auth_mode: str) -> str:
    """Build the real user env without password acquisition settings."""
    from ktem.auth.policy import resolve_auth_mode

    return _build_user_env_template(
        auth_mode=resolve_auth_mode(configured_mode=auth_mode),
        include_password_file_setting=False,
    )


def build_user_env_example() -> str:
    return _build_user_env_template(
        auth_mode="auto",
        include_password_file_setting=True,
    )
