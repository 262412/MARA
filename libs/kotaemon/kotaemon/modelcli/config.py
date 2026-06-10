from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROVIDER_ORDER = [
    "openai",
    "anthropic",
    "gemini",
    "openrouter",
    "local-vllm",
]


@dataclass(slots=True)
class ProviderConfig:
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None

    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None


@dataclass(slots=True)
class RuntimeConfig:
    default_provider: str = "openai"
    provider_order: list[str] = field(
        default_factory=lambda: list(DEFAULT_PROVIDER_ORDER)
    )
    request_timeout: int = 60
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    model_aliases: dict[str, str] = field(default_factory=dict)

    def resolve_model_alias(self, model: str) -> str:
        return self.model_aliases.get(model, model)


def default_config_dict() -> dict[str, Any]:
    return {
        "default_provider": "openai",
        "provider_order": list(DEFAULT_PROVIDER_ORDER),
        "request_timeout": 60,
        "providers": {
            "openai": {"api_key_env": "OPENAI_API_KEY"},
            "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
            "gemini": {"api_key_env": "GOOGLE_API_KEY"},
            "openrouter": {
                "api_key_env": "OPENROUTER_API_KEY",
                "base_url": "https://openrouter.ai/api/v1",
            },
            "local-vllm": {
                "api_key_env": "LOCAL_VLLM_API_KEY",
                "base_url": "http://localhost:8000/v1",
            },
        },
        "model_aliases": {},
    }


def write_default_config(output_path: str | Path, force: bool = False) -> Path:
    path = Path(output_path)
    if path.exists() and not force:
        raise FileExistsError(
            f"Config file already exists at {path}. Use --force to overwrite."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(default_config_dict(), f, sort_keys=False)
    return path


def load_runtime_config(config_path: str | Path | None = None) -> RuntimeConfig:
    base = default_config_dict()
    if config_path:
        path = Path(config_path)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                raise ValueError("Config root must be a mapping/dictionary")
            base = _deep_merge(base, loaded)

    providers: dict[str, ProviderConfig] = {}
    provider_data = base.get("providers", {})
    if not isinstance(provider_data, dict):
        raise ValueError("'providers' must be a mapping/dictionary")

    for name, cfg in provider_data.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"Provider config for {name} must be a mapping/dictionary")
        providers[name] = ProviderConfig(
            api_key=cfg.get("api_key"),
            api_key_env=cfg.get("api_key_env"),
            base_url=cfg.get("base_url"),
        )

    provider_order = base.get("provider_order") or list(DEFAULT_PROVIDER_ORDER)
    if not isinstance(provider_order, list) or any(
        not isinstance(item, str) for item in provider_order
    ):
        raise ValueError("'provider_order' must be a list of provider names")

    model_aliases = base.get("model_aliases") or {}
    if not isinstance(model_aliases, dict):
        raise ValueError("'model_aliases' must be a mapping/dictionary")

    return RuntimeConfig(
        default_provider=base.get("default_provider", "openai"),
        provider_order=provider_order,
        request_timeout=int(base.get("request_timeout", 60)),
        providers=providers,
        model_aliases={str(k): str(v) for k, v in model_aliases.items()},
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
