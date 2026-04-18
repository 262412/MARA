from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import ProviderConfig, RuntimeConfig
from .contracts import ModelRequest, ModelResponse


def _message_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content)


class ProviderAdapter(Protocol):
    name: str

    def is_available(self, cfg: ProviderConfig) -> tuple[bool, str]:
        ...

    def complete(
        self,
        request: ModelRequest,
        runtime_cfg: RuntimeConfig,
        provider_cfg: ProviderConfig,
    ) -> ModelResponse:
        ...


@dataclass(slots=True)
class OpenAICompatibleProvider:
    name: str
    default_base_url: str | None = None

    def is_available(self, cfg: ProviderConfig) -> tuple[bool, str]:
        if cfg.resolved_api_key():
            return True, "available"
        return False, "missing API key"

    def complete(
        self,
        request: ModelRequest,
        runtime_cfg: RuntimeConfig,
        provider_cfg: ProviderConfig,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for this provider") from exc

        api_key = provider_cfg.resolved_api_key()
        if not api_key:
            raise RuntimeError(f"API key not configured for provider '{self.name}'")

        base_url = provider_cfg.base_url or self.default_base_url
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=runtime_cfg.request_timeout,
        )

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        kwargs = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        return ModelResponse(
            text=text,
            provider=self.name,
            model=request.model,
            raw=response,
        )


@dataclass(slots=True)
class AnthropicProvider:
    name: str = "anthropic"

    def is_available(self, cfg: ProviderConfig) -> tuple[bool, str]:
        if cfg.resolved_api_key():
            return True, "available"
        return False, "missing API key"

    def complete(
        self,
        request: ModelRequest,
        runtime_cfg: RuntimeConfig,
        provider_cfg: ProviderConfig,
    ) -> ModelResponse:
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage
        except ImportError as exc:
            raise RuntimeError(
                "langchain-anthropic package is required for anthropic provider"
            ) from exc

        api_key = provider_cfg.resolved_api_key()
        if not api_key:
            raise RuntimeError("API key not configured for provider 'anthropic'")

        llm = ChatAnthropic(
            model=request.model,
            anthropic_api_key=api_key,
            timeout=runtime_cfg.request_timeout,
            temperature=request.temperature,
        )

        messages = [HumanMessage(content=request.prompt)]
        if request.system_prompt:
            messages.insert(0, SystemMessage(content=request.system_prompt))

        response = llm.invoke(messages)
        text = _message_content_to_text(response.content)
        return ModelResponse(
            text=text,
            provider=self.name,
            model=request.model,
            raw=response,
        )


@dataclass(slots=True)
class GeminiProvider:
    name: str = "gemini"

    def is_available(self, cfg: ProviderConfig) -> tuple[bool, str]:
        if cfg.resolved_api_key():
            return True, "available"
        return False, "missing API key"

    def complete(
        self,
        request: ModelRequest,
        runtime_cfg: RuntimeConfig,
        provider_cfg: ProviderConfig,
    ) -> ModelResponse:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain-google-genai package is required for gemini provider"
            ) from exc

        api_key = provider_cfg.resolved_api_key()
        if not api_key:
            raise RuntimeError("API key not configured for provider 'gemini'")

        llm = ChatGoogleGenerativeAI(
            model=request.model,
            google_api_key=api_key,
            timeout=runtime_cfg.request_timeout,
            temperature=request.temperature,
        )

        messages = [HumanMessage(content=request.prompt)]
        if request.system_prompt:
            messages.insert(0, SystemMessage(content=request.system_prompt))

        response = llm.invoke(messages)
        text = _message_content_to_text(response.content)
        return ModelResponse(
            text=text,
            provider=self.name,
            model=request.model,
            raw=response,
        )


class ProviderRegistry:
    def __init__(self, adapters: list[ProviderAdapter]):
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def names(self) -> list[str]:
        return list(self._adapters.keys())

    def get(self, name: str) -> ProviderAdapter:
        adapter = self._adapters.get(name)
        if adapter is None:
            raise ValueError(f"Unknown provider '{name}'")
        return adapter

    def availability(self, cfg: RuntimeConfig) -> dict[str, tuple[bool, str]]:
        report: dict[str, tuple[bool, str]] = {}
        for name, adapter in self._adapters.items():
            provider_cfg = cfg.providers.get(name, ProviderConfig())
            report[name] = adapter.is_available(provider_cfg)
        return report


def build_registry() -> ProviderRegistry:
    adapters: list[ProviderAdapter] = [
        OpenAICompatibleProvider(name="openai"),
        AnthropicProvider(),
        GeminiProvider(),
        OpenAICompatibleProvider(
            name="openrouter", default_base_url="https://openrouter.ai/api/v1"
        ),
    ]
    return ProviderRegistry(adapters)


def infer_provider_from_model(model: str) -> str | None:
    model_lower = model.lower()
    if model_lower.startswith("gpt-") or model_lower.startswith("o1"):
        return "openai"
    if model_lower.startswith("claude-"):
        return "anthropic"
    if model_lower.startswith("gemini-"):
        return "gemini"
    if "/" in model:
        return "openrouter"
    return None


def resolve_provider_name(
    registry: ProviderRegistry,
    cfg: RuntimeConfig,
    model: str,
    provider: str | None = None,
) -> str:
    if provider:
        if provider not in registry.names():
            raise ValueError(f"Unknown provider '{provider}'")
        return provider

    inferred = infer_provider_from_model(model)
    if inferred and inferred in registry.names():
        return inferred

    if cfg.default_provider in registry.names():
        return cfg.default_provider

    for candidate in cfg.provider_order:
        if candidate in registry.names():
            return candidate

    raise ValueError("No provider could be resolved")


def run_completion(
    registry: ProviderRegistry,
    cfg: RuntimeConfig,
    request: ModelRequest,
    provider: str | None = None,
) -> ModelResponse:
    resolved_model = cfg.resolve_model_alias(request.model)
    resolved_request = ModelRequest(
        prompt=request.prompt,
        model=resolved_model,
        system_prompt=request.system_prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    provider_name = resolve_provider_name(
        registry=registry,
        cfg=cfg,
        model=resolved_request.model,
        provider=provider,
    )
    provider_cfg = cfg.providers.get(provider_name, ProviderConfig())
    adapter = registry.get(provider_name)

    available, reason = adapter.is_available(provider_cfg)
    if not available:
        raise RuntimeError(
            f"Provider '{provider_name}' is not available in current environment: {reason}"
        )

    return adapter.complete(resolved_request, cfg, provider_cfg)
