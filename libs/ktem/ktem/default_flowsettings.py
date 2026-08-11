from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from decouple import AutoConfig
from ktem.runtime_bootstrap import get_runtime_paths, load_packaged_runtime_env
from ktem.runtime_defaults import build_kotaemon_settings
from theflow.settings.default import *  # noqa


def _load_user_overrides(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("kotaemon_user_flowsettings", path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: getattr(module, name) for name in dir(module) if name.isupper()}


runtime_paths = get_runtime_paths()
load_packaged_runtime_env()
app_data_dir = Path(
    os.environ.get("KH_APP_DATA_DIR", runtime_paths.data_dir)
).expanduser()
theflow_storage_dir = runtime_paths.cache_dir / "theflow"


def _desktop_embedding_settings(configs: object) -> dict[str, object]:
    if not isinstance(configs, dict):
        return {}
    supported_types = {
        "kotaemon.embeddings.AzureOpenAIEmbeddings",
        "kotaemon.embeddings.OpenAIEmbeddings",
    }
    placeholders = {
        "",
        "<your_openai_key>",
        "your-key",
        "your_api_key",
        "your_key",
    }
    supported: dict[str, object] = {}
    for name, raw_config in configs.items():
        if not isinstance(raw_config, dict):
            continue
        spec = raw_config.get("spec")
        if not isinstance(spec, dict) or spec.get("__type__") not in supported_types:
            continue
        api_key = str(spec.get("api_key") or "").strip().casefold()
        provider_model = spec.get("model") or spec.get("azure_deployment") or ""
        if api_key in placeholders or not str(provider_model).strip():
            continue
        supported[str(name)] = {**raw_config, "spec": dict(spec)}

    default_names = [
        name
        for name, config in supported.items()
        if isinstance(config, dict) and bool(config.get("default"))
    ]
    selected_default = (
        default_names[0]
        if len(default_names) == 1
        else next(
            iter(supported),
            "",
        )
    )
    for name, config in supported.items():
        if isinstance(config, dict):
            config["default"] = name == selected_default
    return supported


if os.environ.get("MARA_DESKTOP_DATA_DIR"):
    runtime_settings = build_kotaemon_settings(
        base_dir=runtime_paths.config_dir,
        app_data_dir=app_data_dir,
        docs_dir=runtime_paths.config_dir / "docs",
        mode="package",
        config_reader=AutoConfig(search_path=str(runtime_paths.config_dir)),
    )
else:
    runtime_settings = build_kotaemon_settings(
        base_dir=runtime_paths.config_dir,
        app_data_dir=app_data_dir,
        docs_dir=runtime_paths.config_dir / "docs",
        mode="package",
    )
runtime_settings.update(_load_user_overrides(runtime_paths.flowsettings_path))
runtime_settings["STORAGE"] = {
    "__type__": "theflow.storage.LocalStorage",
    "prefix": str(theflow_storage_dir),
}
if os.environ.get("MARA_DESKTOP_DATA_DIR"):
    # User overrides may configure models but Desktop selects only providers
    # whose dependencies are part of the native Sidecar bundle.
    runtime_settings["KH_EMBEDDINGS"] = _desktop_embedding_settings(
        runtime_settings.get("KH_EMBEDDINGS")
    )
globals().update(runtime_settings)

KH_SETTINGS_SOURCE = "package-default"
KH_RUNTIME_CONFIG_DIR = runtime_paths.config_dir
KH_RUNTIME_DATA_DIR = runtime_paths.data_dir
KH_RUNTIME_CACHE_DIR = runtime_paths.cache_dir
KH_USER_FLOWSETTINGS_PATH = runtime_paths.flowsettings_path
KH_USER_ENV_PATH = runtime_paths.env_path
